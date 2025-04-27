#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#############################################################################
# Driver for SIM800L module (using AT commands)
# Tested on Raspberry Pi
#############################################################################

import os
import time
import sys
import traceback
import serial
import re
import logging
from datetime import datetime, timedelta
import random
import subprocess
import termios
import tty
import binascii
import gsm0338
import zlib
try:
    from RPi import GPIO
except ModuleNotFoundError:
    GPIO = None

if __package__ == "sim800l":
    from sim800l import pdu
else:
    import pdu


httpaction_method = {
    "0": "GET",
    "1": "POST",
    "2": "HEAD",
    "3": "DELETE",
    "X": "Unknown"
}

httpaction_status_codes = {
    "000": "Unknown HTTPACTION error",
    "100": "Continue",
    "101": "Switching Protocols",
    "200": "OK",
    "201": "Created",
    "202": "Accepted",
    "203": "Non-Authoritative Information",
    "204": "No Content",
    "205": "Reset Content",
    "206": "Partial Content",
    "300": "Multiple Choices",
    "301": "Moved Permanently",
    "302": "Found",
    "303": "See Other",
    "304": "Not Modified",
    "305": "Use Proxy",
    "307": "Temporary Redirect",
    "400": "Bad Request",
    "401": "Unauthorized",
    "402": "Payment Required",
    "403": "Forbidden",
    "404": "Not Found",
    "405": "Method Not Allowed",
    "406": "Not Acceptable",
    "407": "Proxy Authentication Required",
    "408": "Request Time-out",
    "409": "Conflict",
    "410": "Gone",
    "411": "Length Required",
    "412": "Precondition Failed",
    "413": "Request Entity Too Large",
    "414": "Request-URI Too Large",
    "415": "Unsupported Media Type",
    "416": "Requested range not satisfiable",
    "417": "Expectation Failed",
    "500": "Internal Server Error",
    "501": "Not Implemented",
    "502": "Bad Gateway",
    "503": "Service Unavailable",
    "504": "Gateway Time-out",
    "505": "HTTP Version not supported",
    "600": "Not HTTP PDU",
    "601": "Network Error",
    "602": "No memory",
    "603": "DNS Error",
    "604": "Stack Busy",
    "605": "SSL failed to establish channels",
    "606": "SSL fatal alert message with immediate connection termination"
}

ATTEMPT_DELAY = 0.2

def convert_to_string(buf):
    """
    Convert gsm03.38 bytes to string
    :param buf: gsm03.38 bytes
    :return: UTF8 string
    """
    return buf.decode('gsm03.38', errors="ignore").strip()


def convert_gsm(string):
    """
    Encode the string with 3GPP TS 23.038 / ETSI GSM 03.38 codec.
    :param string: UTF8 string
    :return: gsm03.38 bytes
    """
    return string.encode("gsm03.38")


class SIM800L:
    """
    Main class
    """
    uncompleted_mpart = {}

    def __init__(
            self,
            port="/dev/serial0",
            baudrate=115000,
            timeout=3.0,
            write_timeout=300,
            inter_byte_timeout=10,
            mode="PDU"
        ):
        """
        SIM800L Class constructor
        :param port: port name
        :param baudrate: baudrate in bps
        :param timeout: timeout in seconds
        :param mode: can be TEXT, HEX or PDU (default, recommended)
        """
        self.ser = None
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,  # read timeout in seconds
                inter_byte_timeout=inter_byte_timeout,
                write_timeout=write_timeout  # write timeout in seconds
            )
        except serial.SerialException as e:
            # traceback.print_exc(file = sys.stdout)
            # logging.debug(traceback.format_exc())
            logging.critical("SIM800L - Error opening GSM serial port - %s", e)
            return

        fd = self.ser.fileno()
        attr = termios.tcgetattr(fd)
        attr[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attr)
        tty.setraw(fd)

        # Functions:
        self.incoming_action = None
        self.no_carrier_action = None
        self.clip_action = None
        self.msg_action = None

        self._clip = None
        self._msgid = 0
        self.mode = mode

    def check_sim(self):
        """
        Check whether the SIM card has been inserted.
        :return: True if the SIM is inserted, otherwise False; None in case
            of module error.
        """
        sim = self.command_data_ok('AT+CSMINS?')
        if not sim:
            return None
        return re.sub(r'\+CSMINS: \d*,(\d*).*', r'\1', sim) == '1'

    def get_date(self):
        """
        Return the clock date available in the module
        :return: datetime.datetime; None in case of module error.
        """
        date_string = self.command_data_ok('AT+CCLK?')
        if not date_string:
            return None
        logging.debug("SIM800L - date_string: %s", date_string)
        date = re.sub(r'.*"(\d*/\d*/\d*,\d*:\d*:\d*).*', r"\1", date_string)
        logging.debug("SIM800L - date: %s", date)
        try:
            return datetime.strptime(date, '%y/%m/%d,%H:%M:%S')
        except Exception as e:
            logging.error("SIM800L - improper date in '%s': %s", date, e)

    def is_registered(self):
        """
        Check whether the SIM is Registered, home network
        :return: Truse if registered, otherwise False; None in case of module
            error.
        """
        reg = self.command_data_ok('AT+CREG?')
        if not reg:
            return None
        registered = re.sub(r'^\+CREG: (\d*),(\d*)$', r"\2", reg)
        if registered == "1" or registered == "5":
            return True
        return False

    def get_operator(self):
        """
        Display the current network operator that the handset is currently
        registered with.
        :return: operator string; False in case of SIM error. None in case of
            module error.
        """
        operator_string = self.command_data_ok('AT+COPS?')
        operator = re.sub(r'.*"(.*)".*', r'\1', operator_string).capitalize()
        if operator.startswith("+COPS: 0"):
            return False
        return convert_gsm(operator).decode()

    def get_operator_list(self):
        """
        Display a full list of network operator names.
        :return: dictionary of "numeric: "name" fields; None in case of error.
        """
        ret = {}
        operator_string = self.command('AT+COPN\n', lines=0)
        expire = time.monotonic() + 60  # seconds
        while time.monotonic() < expire:
            r = self.check_incoming()
            if not r:
                return None
            if r == ("OK", None):
                break
            if r == ('GENERIC', None):
                continue
            if r[0] != "COPN":
                logging.error("SIM800L - wrong return message: %s", r)
                return None
            ret[r[1]] = r[2]
        return ret

    def get_service_provider(self):
        """
        Get the Get Service Provider Name stored inside the SIM
        :return: string; None in case of module error. False in case of
            SIM error. 
        """
        sprov_string = self.command_data_ok('AT+CSPN?')
        if not sprov_string:
            return None
        if sprov_string == "ERROR":
            return False
        sprov = re.sub(r'.*"(.*)".*', r'\1', sprov_string)
        return convert_gsm(sprov).decode()

    def get_battery_voltage(self):
        """
        Return the battery voltage in Volts
        :return: floating (volts). None in case of module error.
        """
        battery_string = self.command_data_ok('AT+CBC')
        if not battery_string:
            return None
        battery = re.sub(r'\+CBC: \d*,\d*,(\d*)', r'\1', battery_string)
        return int(battery) / 1000

    def get_msisdn(self):
        """
        Get the MSISDN subscriber number
        :return: string;  None in case of module error.
        """

        def parse_cnum_response(response):
            """
            Parse a CNUM response string with the following steps:
            1. Check that it starts with "+CNUM: "
            2. Separate the remaining string
            3. Tokenize fields separated by comma (when outside quotes)
            4. Remove double quotes from strings
            5. Convert the first field from hex to ASCII
            
            Args:
                response (str): The CNUM response string
                
            Returns:
                list: Processed fields or None if invalid format
            """
            # Check if the string starts with "+CNUM: "
            if not response.startswith("+CNUM: "):
                return None
            
            # Remove the prefix
            data = response[7:]
            
            # Tokenize fields (handling commas inside quotes)
            fields = []
            current_field = ""
            in_quotes = False
            
            for char in data:
                if char == '"':
                    in_quotes = not in_quotes
                    current_field += char
                elif char == ',' and not in_quotes:
                    fields.append(current_field)
                    current_field = ""
                else:
                    current_field += char
            
            # Add the last field
            fields.append(current_field.strip())
            
            # Process each field
            processed_fields = []
            for i, field in enumerate(fields):
                # Remove double quotes
                field = field.strip('"')
                
                # Convert first field from hex to ASCII
                if i == 0:
                    try:
                        # Convert hex string to bytes and then to ASCII
                        ascii_value = bytes.fromhex(field).decode('ascii')
                        processed_fields.append(ascii_value)
                    except Exception:
                        # In case of invalid hex, keep original
                        processed_fields.append(field)
                else:
                    processed_fields.append(field)
            
            return processed_fields

        msisdn_string = self.command('AT+CNUM\n')
        if not msisdn_string:
            logging.error("SIM800L - missing return message from get_msisdn")
            return None
        arr = parse_cnum_response(msisdn_string)
        logging.log(5, "SIM800L - sim800l.get_msisdn(): '%s'", arr)
        if not arr or len(arr) < 2:
            logging.error(
                "SIM800L - wrong return message from get_msisdn: %s",
                msisdn_string
            )
            return None
        label = convert_gsm(arr[0]).decode()
        logging.debug("SIM800L - Phone number '%s': %s", label, arr[1])
        if not arr[1]:
            return "Unstored MSISDN"
        return arr[1]

    def get_signal_strength(self):
        """
        Get the signal strength
        :return: number; min = 3, max = 100; None in case of module error.
        """
        signal_string = self.command_data_ok('AT+CSQ')
        if not signal_string:
            return None
        signal = int(re.sub(r'\+CSQ: (\d*),.*', r'\1', signal_string))
        if signal == 99:
            return 0
        return (signal + 1) / 0.32  # min = 3, max = 100

    def get_unit_name(self):
        """
        Get the SIM800 GSM module unit name
        :return: string; None in case of module error.
        """
        return convert_gsm(self.command_data_ok('ATI')).decode()

    def get_hw_revision(self, method=0):
        """
        Get the SIM800 GSM module hw revision
        :return: string; None in case of module error.
        """
        if method == 2:
            return self.command_data_ok('AT+GMR')
        firmware = self.command_data_ok('AT+CGMR')
        if not firmware:
            return None
        if method == 1:
            logging.info("SIM800L - Firmware version: R%s.%s",
                firmware[9:11], firmware[11:13])
            logging.info("SIM800L - Device: %s", firmware[16:23])
            logging.info("SIM800L - Rel: %s", firmware[13:16])
            logging.info("SIM800L - Hardware Model type: %s", firmware[23:])
        return convert_gsm(firmware).decode()

    def get_netlight(self):
        """
        Check whether the SIM800 Net Light Indicator is activated.
        :return: 1 for active, 0 for inactive, False for error.
        """
        try:
            return int(
                re.search(
                    r'\+CNETLIGHT: (\d+)',
                    self.command("AT+CNETLIGHT?\n")
                ).group(1)
            )
        except Exception:
            return False

    def get_serial_number(self):
        """
        Get the SIM800 GSM module serial number
        :return: string; None in case of module error.
        """
        return convert_gsm(self.command_data_ok('AT+CGSN')).decode()

    def get_ccid(self):
        """
        Get the ICCID
        :return: string; None in case of module error.
        """
        return convert_gsm(self.command_data_ok('AT+CCID')).decode()

    def get_imsi(self):
        """
        Get the IMSI
        :return: string; None in case of module error.
        """
        return convert_gsm(self.command_data_ok('AT+CIMI')).decode()

    def get_temperature(self):
        """
        Get the SIM800 GSM module temperature in Celsius degrees
        :return: string; None in case of module error.
        """
        temp_string = self.command_data_ok('AT+CMTE?')
        if not temp_string:
            return None
        temp = re.sub(r'\+CMTE: \d*,([0-9.]*).*', r'\1', temp_string)
        return temp

    def get_flash_id(self):
        """
        Get the SIM800 GSM module flash ID
        :return: string; None in case of module error.
        """
        return convert_gsm(self.command_data_ok('AT+CDEVICE?')).decode()

    def set_date(self):
        """
        Set the Linux system date with the GSM time
        :return: date string; None in case of module error.
        """
        date = self.get_date()
        if not date:
            return None
        date_string = date.strftime('%c')
        with subprocess.Popen(
                ["sudo", "date", "-s", date_string],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT) as sudodate:
            sudodate.communicate()
        return date

    def setup(self, disable_netlight=False):
        """
        Run setup strings for the initial configuration of the SIM800 module
        :return: True if setup is completed; None in case of module error.
        """
        # ATE0          -> command echo off
        # AT+CNETLIGHT=0-> disable net light LED
        # AT+IFC=1,1    -> use XON/XOFF - removed because makes TLS HTTP fail

        # AT+CLIP=1     -> caller line identification
        # AT+CMGF=1     -> plain text SMS
        # AT+CLTS=1     -> enable get local timestamp mode
        # AT+CSCLK=0    -> disable automatic sleep
        # AT+CSCS="GSM" -> Use GSM char set
        # AT+CMGHEX=1   -> Enable or Disable Sending Non-ASCII Character SMS
        for i in range(3):
            ret = self.command('ATE0\n')
            if 'OK' in ret:
                break
            time.sleep(0.1)
            self.ser.write(b'\x1A' + b'\x0a')
            ret = self.command_ok('AT\n')
            time.sleep(0.1)
        if i == 2:
            logging.critical("SIM800L - setup ATE0 failed: %s", ret)
            return None
        if disable_netlight:
            if self.command('AT+CNETLIGHT=0\n') != 'OK':
                logging.critical("SIM800L - AT+CNETLIGHT error")
                return None
        if self.mode == "TEXT":
            setup_string = (
                'AT+IFC=0,0;+CLIP=1;+CMGF=1;+CLTS=1;+CSCLK=0;+CSCS="GSM";+CMGHEX=1\n'
            )  # plain text mode
        elif self.mode == "HEX":
            setup_string = 'AT+CLIP=1;+CMGF=1;+CLTS=1;+CSCLK=0;+CSCS="HEX"\n'  # HEX mode
        elif self.mode == "PDU":
            setup_string = 'AT+CLIP=1;+CMGF=0;+CLTS=1;+CSCLK=0;+CSCS="HEX"\n'  # PDU mode
        else:
            logging.critical(
                "SIM800L - wrong mode initialization: %s (not TEXT, HEX, PDU)",
                hex.mode
            )
            return None
        ret = self.command(setup_string)
        if ret != 'OK':
            logging.critical("SIM800L - setup failed: %s", ret)
            return None
        return True

    def callback_incoming(self, action):
        self.incoming_action = action  # set the callback function

    def callback_no_carrier(self, action):
        self.no_carrier_action = action  # set the callback function

    def callback_msg(self, action):
        self.msg_action = action  # set the callback function

    def callback_clip(self, action):
        self.clip_action = action  # set the callback function

    def get_clip(self):
        """
        Not used
        """
        return self._clip

    def get_msgid(self):
        """
        Return the unsolicited notification of incoming SMS
        :return: number
        """
        return self._msgid

    def set_charset_hex(self):
        """
        Set HEX character set (only hexadecimal values from 00 to FF)
        :return: "OK" if successful, otherwise None
        """
        return self.command_ok('AT+CSCS="HEX"')

    def set_charset_ira(self):
        """
        Set the International reference alphabet (ITU-T T.50) character set
        :return: "OK" if successful, otherwise None
        """
        return self.command_ok('AT+CSCS="IRA"')

    def set_charset_gsm(self):
        """
        Set charset to GSM
        :return: "OK" if successful, otherwise None
        """
        return self.command_ok('AT+CSCS="GSM"')

    def hard_reset(self, reset_gpio):
        """
        This function can only be used on a Raspberry Pi.
        Perform a hard reset of the SIM800 module through the RESET pin
        :param reset_gpio: RESET pin
        :return: True if the SIM is active after the reset, otherwise False
            None in case of module error.
        """
        if not GPIO:
            logging.critical("SIM800L - hard_reset() function not available")
            return None
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(reset_gpio, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.output(reset_gpio, GPIO.HIGH)
        GPIO.output(reset_gpio, GPIO.LOW)
        time.sleep(0.3)
        GPIO.output(reset_gpio, GPIO.HIGH)
        time.sleep(7)
        return self.check_sim()

    def serial_port(self):
        """
        Return the serial port (for direct debugging)
        :return:
        """
        return self.ser

    def send_sms(
        self, destno, msgtext, reference=-1, validity=None, smsc=None,
        requestStatusReport=True, rejectDuplicates=False, sendFlash=False
    ):
        """
        Send SMS message
        :param destno: MSISDN destination number
        :param msgtext: Text message        
        :param reference: used for PDU messages; see pdu.py
        :param validity: used for PDU messages; see pdu.py
        :param smsc: used for PDU messages; see pdu.py
        :param requestStatusReport: used for PDU messages; see pdu.py
        :param rejectDuplicates: used for PDU messages; see pdu.py
        :param sendFlash=False: used for PDU messages; see pdu.py
        :return: True if message is sent, otherwise False
        """
        if reference == -1:
            reference = random.randint(0, 255)
        if not isinstance(reference, (int)) or not (0 <= reference < 256):
            logging.critical(
                "SIM800L - Reference must be an integer between 0 and 255: %s",
                reference
            )
            return False
        if self.mode == "PDU":
            pdu_obj = pdu.encodeSmsSubmitPdu(
                destno, msgtext,
                reference=reference, validity=validity, smsc=smsc,
                requestStatusReport=requestStatusReport,
                rejectDuplicates=rejectDuplicates, sendFlash=sendFlash
            )
            for i in pdu_obj:  # also manages long SMS
                result = self.command(
                    'AT+CMGS={}\n'.format(i.tpduLength),
                    lines=-1,
                    timeout=30,
                    msgpdu=binascii.hexlify(i.data)
                )
                if result == 'OK':
                    continue
                self.ser.write(b'\x1A' + b'\x0a')
                time.sleep(0.1)
                result = self.command(
                    'AT+CMGS={}\n'.format(i.tpduLength),
                    lines=-1,
                    timeout=30,
                    msgpdu=binascii.hexlify(i.data)
                )
                if result == 'OK':
                    continue
                return False
            self.check_incoming()
            return True
        elif self.mode == "HEX":
            result = self.command('AT+CMGS="{}"\n'.format(destno),
                lines=-1,
                timeout=5,
                msgtext=binascii.hexlify(msgtext.encode()).decode()
            )
            if "+CMGS: " in result or '+CUSD' in result:
                logging.warning("SIM800L - New PDU message delivered '%s'", result)
                self.check_incoming()
                return True
            self.check_incoming()
            return False
        elif self.mode == "TEXT":
            result = self.command('AT+CMGS="{}"\n'.format(destno),
                lines=-1,
                timeout=30,
                msgtext=msgtext
            )
            if "+CMGS: " in result or '+CUSD' in result:
                logging.warning("SIM800L - New TEXT message delivered '%s'", result)
                self.check_incoming()
                return True
            self.check_incoming()
            return False
        else:
            logging.critical("SIM800L - invalid mode %s", self.mode)

    def read_sms(self, index_id):
        """
        Read the SMS message referred to the index
        :param index_id: index in the SMS message list starting from 1
        :return: None if error, otherwise return a tuple including:
                MSISDN origin number, SMS date string, SMS time string, SMS text
        """
        result = self.read_next_message(
            all_msg=False, index=index_id, delete=False, tuple=True
        )
        self.check_incoming()
        return result

    def delete_sms(self, index_id):
        """
        Delete the SMS message referred to the index
        :param index_id: index in the SMS message list starting from 1
        :return: None
        """
        self.command('AT+CMGD={}\n'.format(index_id), lines=-1)
        self.check_incoming()

    def get_ip(self, poll_timeout=4):
        """
        Get the IP address of the PDP context.
        Assume that the PDP context is already active.
        :param poll_timeout: optional poll setting in seconds to wait for the
            IP address to return as +SAPBR: 1,1,"...".
        :return: valid IP address string if the bearer is connected,
            otherwise `None`. If error: `False`.
        """
        ip_address = False
        expire = time.monotonic() + poll_timeout  # seconds
        s = None
        while time.monotonic() < expire:
            buf = self.command('AT+SAPBR=2,1\n', lines=-1)
            if not buf:
                time.sleep(0.1)
                continue
            s = self.decode_cmd_response(buf)
            if s[0] == 'IP':
                ip_address = s[1]
                break
            time.sleep(0.1)
        if ip_address == False:
            logging.warning(
                "SIM800L - no data returned from get_ip(): %s, %s", buf, s
            )
            return False
        if ip_address == None or ip_address == '0.0.0.0':
            logging.debug("SIM800L - NO IP Address")
            return None
        logging.debug("SIM800L - Returned IP Address: %s", ip_address)
        return ip_address

    def disconnect_gprs(self, apn=None):
        """
        Disconnect the bearer.
        :return: True if successful, False if error
        """
        return self.command_ok('AT+SAPBR=0,1')

    def connect_gprs(self, apn=None):
        """
        Connect to the bearer and get the IP address of the PDP context.
        Automatically perform the full PDP context setup.
        Reuse the IP session if an IP address is found active.
        :param apn: APN name
        :return: False if error, otherwise return the IP address (as string)

        Initialization and connection:

        AT+SAPBR=3,1,"CONTYPE","GPRS" - sets bearer profile 1’s connection type
            to GPRS
        AT+SAPBR=3,1,"APN","..." - sets the APN for profile 1 to "..."
        AT+SAPBR=1,1 - opens (activates) the GPRS context using bearer profile
            1 with the parameters set above

        Error genarally means wrong APN.
        Successs (PDP context created) is shown by a Fast flash of the LED

        Query:
        AT+SAPBR=2,1 - query IP address

        Disconnection:

        AT+SAPBR=0,1 - closes (deactivates) the bearer profile 1, terminating
            the GPRS session.
        """
        if apn is None:
            logging.critical("SIM800L - Missing APN name")
            return False
        ip_address = self.get_ip()
        if ip_address is False:
            logging.error(
                "SIM800L - no answer from get_ip() in connect_gprs()"
            )
            return False
        if ip_address:  # already connected
            logging.info("SIM800L - Already connected: %s", ip_address)
        else:
            r = self.command_ok(
                'AT+SAPBR=3,1,"CONTYPE","GPRS";+SAPBR=3,1,"APN","' +
                apn + '";+SAPBR=1,1',
                check_error=True)
            if r == "ERROR":
                logging.error("SIM800L - Cannot connect to GPRS")
                return False
            """
            if not r:
                logging.error(
                    "SIM800L - no answer from sim800l.connect_gprs()"
                )
                return False
            """
            ip_address = self.get_ip()
            if not ip_address:
                logging.error("SIM800L - Cannot connect bearer")
                return False
            logging.debug("SIM800L - Bearer connected")
        return ip_address

    def query_ip_address(self,
            url=None,
            apn=None,
            http_timeout=10,
            keep_session=False):
        """
        Connect to the bearer, get the IP address and query an internet domain
        name, getting the IP address.
        Automatically perform the full PDP context setup.
        Disconnect the bearer at the end (unless keep_session = True)
        Reuse the IP session if an IP address is found active.
        :param url: internet domain name to be queried
        :param http_timeout: timeout in seconds
        :param keep_session: True to keep the PDP context active at the end
        :return: False if error, otherwise the returned IP address (string)
        """
        if not url:
            logging.error("SIM800L - missing URL parameter")
            return False
        ip_address = self.connect_gprs(apn=apn)
        r = self.command('AT+CIFSR\n')
        if not r:
            return None
        if r == 'ERROR':
            if ip_address is False:
                if not keep_session:
                    self.disconnect_gprs()
                return False
            if not self.command_ok('AT+CSTT="' + apn + '";+CIICR'):
                self.command('AT+CIPSHUT\n')
                if not keep_session:
                    self.disconnect_gprs()
                return False
        logging.info("SIM800L - IP Address: %s", self.command('AT+CIFSR\n'))
        cmd = 'AT+CDNSGIP="' + url + '"'
        if not self.command_ok(cmd):
            logging.error("SIM800L - error while querying DNS")
            self.command('AT+CIPSHUT\n')
            if not keep_session:
                self.disconnect_gprs()
            return False
        expire = time.monotonic() + http_timeout
        s = self.check_incoming()
        if not s:
            return None
        dns = False
        while time.monotonic() < expire:
            if s[0] == 'DNS':
                if not s[1]:
                    logging.error(
                        "SIM800L - error while querying DNS: %s", s[2])
                    self.command('AT+CIPSHUT\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False
                dns = s[1]
                logging.info("SIM800L - DNS: %s", dns)
                break
            time.sleep(0.1)
            s = self.check_incoming()
            if not s:
                return None
        self.command('AT+CIPSHUT\n')
        if not keep_session:
            self.disconnect_gprs()
        return dns

    def internet_sync_time(self,
            time_server="193.204.114.232",  # INRiM NTP server
            time_zone_quarter=4,  # 1/4 = UTC+1
            apn=None,
            http_timeout=10,
            keep_session=False):
        """
        Connect to the bearer, get the IP address and sync the internal RTC with
        the local time returned by the NTP time server (Network Time Protocol).
        Automatically perform the full PDP context setup.
        Disconnect the bearer at the end (unless keep_session = True)
        Reuse the IP session if an IP address is found active.
        :param time_server: internet time server (IP address string)
        :param time_zone_quarter: time zone in quarter of hour
        :param http_timeout: timeout in seconds
        :param keep_session: True to keep the PDP context active at the end
        :return: False if error, otherwise the returned date (datetime.datetime)
        """
        ip_address = self.connect_gprs(apn=apn)
        if ip_address is False:
            if not keep_session:
                self.disconnect_gprs()
            return False
        cmd = 'AT+CNTP="' + time_server + '",' + str(time_zone_quarter)
        if not self.command_ok(cmd):
            logging.error("SIM800L - sync time did not return OK.")
        if not self.command_ok('AT+CNTP'):
            logging.error("SIM800L - AT+CNTP did not return OK.")
        expire = time.monotonic() + http_timeout
        s = self.check_incoming()
        ret = False
        while time.monotonic() < expire:
            if s[0] == 'NTP':
                if not s[1]:
                    logging.error("SIM800L - Sync time error %s", s[2])
                    if not keep_session:
                        self.disconnect_gprs()
                    return False
                ret = True
                break
            time.sleep(0.1)
            s = self.check_incoming()
        if ret:
            logging.debug("SIM800L - Network time sync successful")
            ret = self.get_date()
        if not keep_session:
            self.disconnect_gprs()
        return ret

    def http(self,
             url=None,
             data=None,
             apn=None,
             method=None,
             use_ssl=False,
             ua=None,
             content_type="application/json",
             binary=False,
             allow_redirection=False,
             http_timeout=120,
             keep_session=False,
             attempts=2):
        """
        Run the HTTP GET method or the HTTP POST method and return retrieved data.
        Automatically perform the full PDP context setup and close it at the end
        (use keep_session=True to keep the IP session active). Reuse the IP
        session if an IP address is found active.
        Automatically open and close the HTTP session, resetting errors.
        :param url: URL
        :param data: input data used for the POST method (bytes)
        :param apn: APN name
        :param method: GET or POST (or PUT)
        :param use_ssl: True if using HTTPS, False if using HTTP; note:
            The SIM800L module only supports  SSL2, SSL3 and TLS 1.0.
        :param ua: User agent (string); is not set, the SIM800L default user
            agent is used ("SIMCom_MODULE").
        :param content_type: (string) set the "Content-Type" field in the HTTP
            header.
        :param binary: if True, return binary bytes, otherwise return UTF8 text.
        :param allow_redirection: True if HTTP redirection is allowed (e.g., if
            the server sends a redirect code (range 30x), the client will
            automatically send a new HTTP request)
        :param http_timeout: timeout in seconds
        :param keep_session: True to keep the PDP context active at the end
        :param attempts: number of attempts before returning False
        :return: False, None if error, otherwise return a tuple including
            two values: status code and returned data (as string)

        Protocol Description:

        AT+HTTPINIT - initializes the HTTP service, preparing the module to
            use the HTTP functions.
        AT+HTTPPARA="CID",1 - sets the HTTP parameter "CID" (Connection
            Identifier) to 1. This tells the module which bearer profile
            (or GPRS context) to use for the HTTP session.

        AT+HTTPPARA="URL","httpbin.org/ip" - sets the URL parameter for the
            HTTP session.

        AT+HTTPPARA="REDIR",0 - Configures redirection handling. A value of 0
            disables automatic redirection, meaning the module won’t follow
            HTTP 3xx responses automatically.
        AT+HTTPPARA="REDIR",1 - allows redirection

        AT+HTTPSSL=0 - specifies whether the HTTP session should use SSL/TLS.
            Setting it to 0 indicates that the connection will not be secured
            (i.e. it will use plain HTTP).
        AT+SSLOPT=1,0 means not need client authentication
        AT+SSLOPT=0,1 means not need server authentication
        AT+HTTPSSL=1;+SSLOPT=0,1;+SSLOPT=1,0 - allows SSL

        """
        # Check valid parameters
        if url is None:
            logging.critical("SIM800L - Missing HTTP url")
            return False, None
        if method is None:
            logging.critical("SIM800L - Missing HTTP method")
            return False, None
        if method == "POST" or method == "PUT":
            method = "POST"
            # POST data must exist
            if not data:
                logging.critical("SIM800L - Null data parameter.")
                return False, None
            # POST data must be bytes
            if not isinstance(data, (bytes, bytearray)):
                logging.critical("SIM800L - data must be bytes.")
                return False, None
        if attempts < 1:
            logging.critical("SIM800L - attempts must be at least 1")
            return False, None

        current_try = attempts
        while current_try >= 0:
            if current_try != attempts:  # Reset communication for all subsequent attempts
                logging.warning(
                    "SIM800L - New attempt %s/%s", current_try, attempts
                )
                time.sleep(0.1)
                # Try to exit from HTTPINIT so that it can be performed again
                r = self.command_ok('AT+HTTPTERM', check_error=True)  # returns ERROR in normal conditions
                if r != "ERROR":
                    logging.warning(
                        "SIM800L - Recovered broken AT+HTTPINIT (returning %s)",
                        repr(r)
                    )
                if not current_try:
                    return False, None
                # Try disconnecting GPRS so that it can then reconnect
                self.disconnect_gprs()
                time.sleep(0.1)
            current_try -= 1

            # Connect GPRS
            ip_address = self.connect_gprs(apn=apn)
            if ip_address is False:
                if not keep_session:
                    self.disconnect_gprs()
                return False, None

            # Start HTTP session (will fail if HTTPINIT was already issued before without subsequent HTTPTERM)
            ri = self.command('AT+HTTPINIT\n')
            if ri != 'OK':
                # First try to exit from a previous broken HTTP without cycling the whole GPRS connection
                time.sleep(0.1)
                self.command('AT+HTTPTERM\n')
                time.sleep(0.1)
                r = self.command('AT+HTTPINIT\n')
                if r == 'OK':
                    logging.warning(
                        "SIM800L - AT+HTTPINIT recovery from %s", repr(ri)
                    )
                else:
                    # Here HTTPINIT continues to fail: prepare the whole connection cycle
                    logging.warning(
                        "SIM800L - AT+HTTPINIT error: %s (previous one: %s)",
                        repr(r), repr(ri)
                    )
                    self.command('AT+HTTPTERM\n')
                    continue

            # Prepare HTTPPARA for REDIR and UA; add SSL option
            allow_redirection_string = ';+HTTPPARA="REDIR",0'
            if allow_redirection:
                allow_redirection_string = ';+HTTPPARA="REDIR",1'
            use_ssl_string = ';+HTTPSSL=0'
            if use_ssl:
                use_ssl_string = ';+HTTPSSL=1;+SSLOPT=0,1;+SSLOPT=1,0'
            if ua:
                ua_string = ';+HTTPPARA="UA","' + ua + '"'
            else:
                ua_string = ""

            # Complete preparation of HTTPPARA for CID, URL, CONTENT
            cmd = (  # POST
                'AT+HTTPPARA="CID",1'
                ';+HTTPPARA="URL","' + url + '"' + ua_string +
                ';+HTTPPARA="CONTENT","' + content_type + '"' +
                allow_redirection_string + use_ssl_string
            )
            if method == "GET":
                cmd = (  # GET
                    'AT+HTTPPARA="CID",1;+HTTPPARA="URL","' + url +
                    '"' + allow_redirection_string + use_ssl_string
                )

            # Perform HTTP configuration
            r = self.command_ok(cmd, check_error=True)
            if r != True:
                logging.error(
                    "SIM800L - AT+HTTPPARA error. Retrying: %s", repr(r)
                )
                continue

            # Disable flow contol
            r = self.command_ok('AT+IFC=0,0')
            if r != True:
                logging.error(
                    "SIM800L - AT+IFC error. Retrying: %s", repr(r)
                )
                continue

            if method == "POST":
                # Ask to send POST data (HTTPDATA)
                len_input = len(data)
                cmd = 'AT+HTTPDATA=' + str(len_input) + ',' + str(
                    http_timeout * 1000
                )
                r = self.command_ok(cmd, check_download=True, check_error=True)
                # Wait for "DOWNLOAD"
                if r == "ERROR":
                    logging.critical("SIM800L - AT+HTTPDATA returned ERROR.")
                    self.command('AT+HTTPTERM\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False, None
                if r != "DOWNLOAD":
                    logging.error(
                        "SIM800L - Missing 'DOWNLOAD' return message: %s", r
                    )
                    continue
                # Write POST data
                logging.debug("SIM800L - Writing data; length = %s", len_input)
                try:
                    write_bytes = self.ser.write(data + '\n'.encode())
                except Exception as e:
                    logging.error("SIM800L - http write error: %s", e)
                    self.command('AT+HTTPTERM\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False, None
                # Check that all data are written in one take
                if write_bytes != len(data) + 1:
                    logging.error(
                        "SIM800L - written %s bytes instead of %s.",
                        write_bytes, len(data)
                    )
                    self.command('AT+HTTPTERM\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False, None
                # Wait for OK (can take long)
                expire = time.monotonic() + http_timeout
                s = self.check_incoming()
                while s == ('GENERIC', None) and time.monotonic() < expire:
                    time.sleep(0.1)
                    s = self.check_incoming()
                if s != ("OK", None):
                    logging.error(
                        "SIM800L - missing OK after writing POST data %s.", s
                    )
                    continue
                # Execute the POST (HTTPACTION)
                r = self.command_ok('AT+HTTPACTION=1')  # POST
                if not r:
                    self.command('AT+HTTPTERM\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False, None
            if method == "GET":
                # Execute the GET (HTTPACTION)
                r = self.command_ok('AT+HTTPACTION=0')  # GET
                if not r:
                    self.command('AT+HTTPTERM\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False, None

            # Wait for the the HTTPACTION answer until http_timeout (can take long)
            expire = time.monotonic() + http_timeout
            s = self.check_incoming()
            while s[0] != 'HTTPACTION_' + method and time.monotonic() < expire:
                time.sleep(0.1)
                s = self.check_incoming()
            if s[0] != 'HTTPACTION_' + method:
                logging.error("Improper answer to AT+HTTPACTION: %s", s)
                continue

            # Decode the read status code and the read buffer size from HTTPACTION answer
            status_code = s[1]  # status code (True if 200, 3xx)
            len_read = s[2]  # read buffer size
            if len_read == 0:
                logging.debug("SIM800L - no data to be retrieved: %s", s)
            if not status_code:
                logging.debug("SIM800L - invalid request: %s", s)
                self.command('AT+HTTPTERM\n')
                if not keep_session:
                    self.disconnect_gprs()
                return status_code, None

            # Read the first line (HTTPREAD)
            r = self.command('AT+HTTPREAD\n', lines=1)
            logging.log(5, "SIM800L - HTTPREAD answer: %s", repr(r))
            params = r.strip().split(':')
            if (len(params) == 2 and
                    params[0] == '+HTTPREAD' and
                    params[1].strip().isnumeric()):
                length_of_read_data = int(params[1].strip())
                if len_read != length_of_read_data:
                    logging.critical(
                        "SIM800L - Different number of read characters:"
                        " %d != %d",
                        len_read, length_of_read_data)
                    self.command('AT+HTTPTERM\n')
                    if not keep_session:
                        self.disconnect_gprs()
                    return False, None
            # Read the subsequent lines
            ret_data = b''  # Binary data
            expire = time.monotonic() + http_timeout
            while len(ret_data) < len_read and time.monotonic() < expire:
                ret_data += self.ser.read(len_read)
            logging.debug("SIM800L - Returned data: '%s'", repr(ret_data))
            # Read the last OK message
            r = self.check_incoming()
            if len(ret_data):
                # fix the possibility that OK is included in ret_data
                if r != ("OK", None) and ret_data[-5:].decode(
                    encoding='utf-8', errors='ignore'
                ).strip() == 'OK':
                    r = ("OK", None)
                    ret_data = ret_data[:-6]
                # do another attempt cycle if OK is missing
                if r != ("OK", None):
                    continue

            # If OK is received, compare read data with buffer size
            if len(ret_data) != len_read:
                logging.warning(
                    "SIM800L - Length of returned data: %d. Expected: %d",
                    len(ret_data), len_read)
            # Close session
            r = self.command_ok('AT+HTTPTERM')
            if not r:
                self.command('AT+HTTPTERM\n')
                if not keep_session:
                    self.disconnect_gprs()
                return False, None
            # Disconnect GPRS
            if not keep_session:
                if not self.disconnect_gprs():
                    self.command('AT+HTTPTERM\n')
                    self.disconnect_gprs()
                    return False, None
            if binary:
                return status_code, ret_data
            else:
                return status_code, ret_data.decode(
                    encoding='utf-8', errors='ignore'
                )
        logging.critical(
            "SIM800L - invalid number of attempts: %s/%s", current_try, attempts
        )
        return False, None

    def read_and_delete_all(self, index_id=0, delete=True):
        """
        Read the first message, then delete all SMS messages, regardless
        the type (read, unread, sent, unsent, received)
        :return: text of the message
        """
        ret = self.read_next_message(
            all_msg=False, index=index_id, delete=delete
        )
        if delete:
            if self.mode == "PDU":
                self.command('AT+CMGDA=6\n', lines=-1)
            else:
                self.command('AT+CMGDA="DEL ALL"\n', lines=-1)
        self.check_incoming()
        return ret

    def decode_sms_response(self, response):
        """
        Decode SMS messages in TEXT, HEX or PDU form. Process multipart PDU
        messages, assembling the full test of a complete multipart message
        and marking as invalid uncomplete multiparts.
        
        Only the last part of a complete multipart message has the whole message
        text (assembly of all the parts) and is marked as valid. All the other
        parts have partial text and are marked as non valid.
        
        The case where all parts of a multipart message are non valid means that
        the some part is still to be received. If only one part of a multimpart
        message is valid, the whole multipart is received.

        :param response: multi-line string containing a sequence of textual
        +CMGL responses (more messages)
        :return: array of dictionaries including all decoded messages

        Dictionary keys in TEXT and HEX modes: 'header', 'text'
        Dictionary keys in PDU mode: 'header', 'multipart', 'text', 'valid'
        """
        decoded_messages = []
        current_message = {}

        multipart = {}
        for line in response.split('\n'):
            line = line.strip()
            if not line or line == "OK":
                continue
                
            if line.startswith('+CMGL:'):
                if current_message:
                    decoded_messages.append(current_message)
                    current_message = {}
                
                # Parse and decode sender information
                parts = [
                    int(p) if p.strip().isdigit()
                    else p.strip().strip('"') for p in line.split(',', 4)
                ]
                if self.mode == "PDU":
                    try:
                        message_number = int(parts[0].split()[1])
                    except Exception:
                        message_number = 0
                    logging.debug("SIM800L - Message n. %s", message_number)
                    parts[0] = message_number
                elif self.mode == "HEX":
                    try:
                        # Decode sender number from hex
                        sender_hex = parts[2]
                        sender_bytes = bytes.fromhex(sender_hex)
                        decoded_sender = convert_to_string(sender_bytes)
                        parts[2] = decoded_sender
                        try:
                            message_number = int(parts[0].split()[1])
                        except Exception:
                            message_number = 0
                        logging.debug("SIM800L - Message n. %s", message_number)
                        parts[0] = message_number
                    except (ValueError, IndexError):
                        pass
                elif self.mode == "TEXT":
                    try:
                        message_number = int(parts[0].split()[1])
                    except Exception:
                        message_number = 0
                    logging.debug("SIM800L - Message n. %s", message_number)
                    parts[0] = message_number
                else:
                    logging.critical("SIM800L - invalid mode %s", self.mode)
                
                current_message["header"] = parts

            else:
                cmd = self.decode_cmd_response(line)
                if not cmd or cmd[0] != 'GENERIC':
                    continue
                if self.mode == "PDU":
                    try:
                        # Attempt to decode the SMS PDU string; decodeSmsPdu returns a dict with with all decoded SMS fields like sender, time, etc., including UDH if present.
                        try:
                            decoded_sms = pdu.decodeSmsPdu(line)
                        except Exception as e:
                            logging.error("SIM800L - cannot decode PDU '%s': %s", line, e)
                            continue

                        # Store raw PDU
                        current_message["PDU"] = line

                        # Insert decoded SMS timestamp (formatted) into the header
                        try:
                            current_message["header"].insert(
                                1, decoded_sms["time"].strftime('%y/%m/%d,%H:%M:%S')
                                + decoded_sms["time"].strftime('%z')[:3]
                            )
                        except Exception:
                            current_message["header"].insert(1, "")

                        # Insert SMSC (Service Center Address) into header
                        try:
                            current_message["header"].insert(1, decoded_sms["smsc"])
                        except Exception:
                            current_message["header"].insert(1, "")

                        # Insert sender's number into header
                        try:
                            current_message["header"].insert(1, decoded_sms["number"])
                        except Exception:
                            current_message["header"].insert(1, "")

                        # Insert message type into header
                        try:
                            current_message["header"].insert(1, decoded_sms["type"])
                        except Exception:
                            current_message["header"].insert(1, "")

                        # Initialize multipart flag (default: False)
                        try:
                            current_message["multipart"] = False
                        except Exception:
                            current_message["header"].insert(1, "")

                        # Check for User Data Header (UDH), which may indicate multipart SMS
                        if "udh" in decoded_sms:
                            for ie in decoded_sms["udh"]:
                                # Check if UDH contains concatenation info (multipart SMS)
                                if isinstance(ie, pdu.Concatenation):
                                    # Validate consistency of total parts for the same reference
                                    if ie.reference in multipart and multipart[ie.reference]["total"] != ie.parts:
                                        logging.error(
                                            "SIM800L - Reference: %s. previous total = %s, current total = %s",
                                            ie.reference, multipart[ie.reference]["total"], ie.parts
                                        )
                                        current_message["valid"] = False

                                    # Initialize reference entry if not present
                                    if ie.reference not in multipart:
                                        multipart[ie.reference] = {}

                                    # Mark message as part of multipart
                                    current_message["multipart"] = ie.reference

                                    # Track total parts and this part's content
                                    multipart[ie.reference]["total"] = ie.parts
                                    multipart[ie.reference][ie.number - 1] = decoded_sms["text"]
                                    logging.debug(
                                        "SIM800L - Reference: %s. Total parts: %s. Sequence number: %s. Text: %s",
                                        ie.reference, ie.parts, ie.number, decoded_sms["text"]
                                    )
                                    # Progressively populates the multipart[ie.reference]
                                    # dictionary as each part of a multipart SMS is received.

                            # Attempt to reconstruct full message concatenating all parts collected so far
                            text = ""
                            for i in range(multipart[ie.reference]["total"]):
                                if i in multipart[ie.reference]:
                                    logging.log(
                                        5,
                                        "SIM800L - %s: %s - Text: %s",
                                        i, ie.reference, multipart[ie.reference]
                                    )
                                    # Concatenate message segments in sequence to reconstruct full multipart SMS
                                    text += multipart[ie.reference][i]
                                else:
                                    # A part is missing; mark message as invalid
                                    logging.log(
                                        5,
                                        "SIM800L - %s: not present in %s - %s",
                                        i, ie.reference, multipart[ie.reference]
                                    )
                                    i = -1  # exit from this loop before continuing the outer one
                                    break
                            # If not all parts were present, skip further processing
                            if i == -1:
                                # Only partial text is stored and parts are non valid.
                                # The initial part of the message is anyway valid.
                                # If the initial part is missing, "" is stored even
                                # if subsequent parts are available.
                                current_message["text"] = text
                                current_message["valid"] = False
                                continue  # here the outer loop is continued

                            # All parts received; store complete text and mark as valid.
                            # The case where all parts are available happens
                            # only for the last part that completes the set.
                            logging.log(
                                5,
                                "SIM800L - Full text for reference %s of %s parts: %s",
                                ie.reference, ie.parts, text
                            )
                            current_message["text"] = text
                            current_message["valid"] = True
                            continue  # end of UDH

                        # For single-part SMS where UDH is not present
                        if "text" in current_message:
                            logging.error(
                                "SIM800L - duplicated line while decoding PDU %s",
                                decoded_sms
                            )
                            current_message["text"] += decoded_sms["text"]
                        else:
                            # Assign text of single-part SMS
                            current_message["text"] = decoded_sms["text"]

                        # Mark current message as valid
                        current_message["valid"] = True
                    except Exception as e:
                        logging.exception("SIM800L - Error decoding PDU: %s", e)
                elif self.mode == "HEX":
                    # Decode message content from hex
                    try:
                        content_bytes = bytes.fromhex(line)
                        decoded_content = convert_to_string(content_bytes)
                        if "text" in current_message:
                            logging.error(
                                "SIM800L - duplicated line while decoding HEX %s: %s",
                                current_message, decoded_content
                            )
                            current_message["text"] += decoded_content
                        else:
                            current_message["text"] = decoded_content
                    except ValueError as e:
                        logging.error("SIM800L - Error decoding HEX: %s", e)
                        current_message["raw"] = line  # Fallback to raw hex
                elif self.mode == "TEXT":
                        if "text" in current_message:
                            current_message["text"] += ('\n' + line)
                        else:
                            current_message["text"] = line
                else:
                    logging.critical("SIM800L - invalid mode: %s", self.mode)
                    current_message["raw"] = line

        if current_message:
            decoded_messages.append(current_message)
            
        return decoded_messages

    def read_next_message(
        self,
        all_msg=False, index=0, delete=True, tuple=False, concatenate=False,
        delta_min=15
    ):
        """
        Check messages, read one message and then delete it.
        Can be repeatedly called to read messages one by one and delete them.
        Aggregate multipart PDU messages.
        Only delete messages if there are no errors.

        :param all_msg: True if no filter is used (return both read and non read
            messages). Otherwise, only the non read messages are returned.
        :param index: read index message in processed array; default is the first one.
        :param delete: delete the message after reading it.
        :param tuple: returns a tuple instead of the plain text. Tuple:
            [MSISDN origin number, SMS date string, SMS time string, SMS text]
        :param concatenate: concatenate text messages (text mode) when read
            message is > 150 chars. Not reliable (suggest using PDU mode)
        :param delta_min: max time in minutes to keep uncompleted multipart
            undecoded (allowing to wait for its completion)
        :return: retrieved message text (string), otherwise: None = no messages
            to read; False = read error
        """
        def msg_is_multipart(msg):
            return (
                "multipart" in msg
                and msg["multipart"] != None
                and msg["multipart"] != False
                and (
                        isinstance(msg["multipart"], int)
                        or msg["multipart"].isnumeric()
                    )
            )

        def delete_messages(to_delete):
            if delete:
                for i in to_delete:
                    logging.debug("SIM800L - Deleting SMS message %s", i)
                    self.delete_sms(i)

        def produce_tuple(msg):
            try:
                origin = msg["header"][2]
            except Exception:
                origin = ""
            try:
                date_string = msg["header"][4].split(",")[0]
            except Exception:
                date_string = ""
            try:
                time_string = msg["header"][4].split(",")[1]
            except Exception:
                time_string = ""
            try:
                text = msg["text"]
            except Exception:
                text = ""
            return [origin, date_string, time_string, text]

        # Invoke command to read SMS
        # AT+CMGL=4,1: List All SMS messages from the preferred storage in PDU mode.
        # AT+CMGL=0,1: List Received Unread SMS messages from the preferred storage in PDU mode.
        # Messages with status 'received unread' are listed without changing their status.
        if self.mode == "PDU" and concatenate:
            logging.error("SIM800L - concatenate not accepted for PDU mode")
            return False
        for i in range(2):
            if all_msg:
                if self.mode == "PDU":
                    sms_data = self.command('AT+CMGL=4,1\n', lines=-1)  # PDU mode
                else:
                    sms_data = self.command('AT+CMGL="ALL",1\n', lines=-1)  # text or hex mode
            else:
                if self.mode == "PDU":
                    sms_data = self.command('AT+CMGL=0,1\n', lines=-1)  # PDU mode
                else:
                    sms_data = self.command('AT+CMGL="REC UNREAD",1\n', lines=-1)  # text or hex mode
            if sms_data == "OK":
                return None
            if sms_data:
                break
            logging.error("SIM800L - failure while reading SMS messages")
            time.sleep(0.1)
            self.ser.write(b'\x1A' + b'\x0a')
            time.sleep(0.1)
        if not sms_data:
            return False
        #print(sms_data)
        decoded_messages = self.decode_sms_response(sms_data)

        """
        for idx, msg in enumerate(decoded_messages, 1):
            print(f"Message {idx}:")
            print(msg)
            print("\n" + "-"*50 + "\n")
        """

        to_delete = set()
        if not decoded_messages:
            logging.error("SIM800L - failure while decoding SMS messages")
            return False
        for msg in decoded_messages:
            if "header" not in msg:
                logging.error(
                    "SIM800L - missing header in msg: %s", msg
                )
                return False
            try:
                msg_num = msg["header"][0]
            except Exception:
                logging.error(
                    "SIM800L - missing header [0] in msg: %s", msg
                )
                return False
            if not isinstance(msg_num, int):
                logging.error(
                    "SIM800L - header [0] not integer in msg: %s", msg
                )
                return False

            if self.mode == "PDU":
                if "valid" not in msg or "multipart" not in msg:
                    logging.error(
                        "SIM800L - improper format of decoded PDU SMS: %s", msg
                    )
                    if "text" in msg:
                        to_delete.add(msg_num)
                        delete_messages(to_delete)
                        if tuple:
                            return produce_tuple(msg)
                        return msg["text"]
                    logging.error(
                        "SIM800L - missing text in improper format of decoded PDU message: %s",
                        msg
                    )
                    continue
                has_multipart = msg_is_multipart(msg)
                if msg["valid"] and not has_multipart:  # standard valid message
                    if "text" in msg:
                        to_delete.add(msg_num)
                        delete_messages(to_delete)
                        if tuple:
                            return produce_tuple(msg)
                        return msg["text"]
                    logging.error(
                        "SIM800L - missing text in valid PDU message: %s", msg
                    )
                    continue
                if not msg["valid"] and not has_multipart:
                    logging.error(
                        "SIM800L - missing multipart for invalid PDU SMS: %s",
                        msg
                    )
                    return False
                if has_multipart:  # process valid and non valid multipart messages
                    multipart = msg["multipart"]
                    # Check that this multipart is completed somewhere; if a valid part is found and has a text element, process it 
                    for i in decoded_messages:
                        # if a multipart message is completed
                        if "valid" in i and "multipart" in i and i["valid"] and i["multipart"] == multipart:
                            if "text" in i:
                                # Remove each of the parts of a complete multipart message, regardless the related decoded dict is valid
                                for part in decoded_messages:
                                    if "multipart" in part and part["multipart"] == multipart:
                                        if "header" not in part:
                                            logging.error(
                                                "SIM800L - missing header in multipart msg: %s", part
                                            )
                                            return False
                                        # get the message number (the first element of the header list) to remove the message
                                        try:
                                            msg_num = part["header"][0]
                                        except Exception:
                                            logging.error(
                                                "SIM800L - missing header [0] in multipart msg: %s", part
                                            )
                                            return False
                                        if not isinstance(msg_num, int):
                                            logging.error(
                                                "SIM800L - header [0] not integer in multipart msg: %s", part
                                            )
                                            return False
                                        # remove each part of a mutipart message
                                        to_delete.add(msg_num)
                                delete_messages(to_delete)
                                if tuple:
                                    return produce_tuple(i)
                                return i["text"]
                            logging.error(
                                "SIM800L - missing text in valid multipart PDU SMS: %s",
                                msg
                            )
                    # Uncompleted multipart SMS (save to self.uncompleted_mpart)
                    if "PDU" not in i:
                        logging.error(
                            "SIM800L - invalid and uncompleted multipart SMS: %s", i
                        )
                        continue
                    try:
                        notz_date = i["header"][4].split('+')[0]
                        i["recv_date"] = datetime.strptime(notz_date, '%y/%m/%d,%H:%M:%S')
                    except Exception:
                        i["recv_date"] = datetime.now()
                    if i["recv_date"].year < 2022:  # fix possibly wrong PDU date
                        i["recv_date"] = datetime.now()
                    if i["PDU"] not in self.uncompleted_mpart:
                        self.uncompleted_mpart[i["PDU"]] = i

                    # If uncompleted multipart is old, return it anyway
                    if self.uncompleted_mpart[i["PDU"]]["recv_date"] + timedelta(minutes=delta_min) < datetime.now():
                        del self.uncompleted_mpart[i["PDU"]]
                        to_delete.add(msg_num)
                        delete_messages(to_delete)
                        if "text" not in i:
                            i["text"] = ""
                        logging.error("SIM800L - returned multipart SMS is not completed: %s", i)
                        if tuple:
                            return produce_tuple(i)
                        return i["text"]

                    logging.debug("SIM800L - multipart SMS not completed yet: %s", i)

            if "text" in msg and not msg_is_multipart(msg):  # non PDU
                to_delete.add(msg_num)
                message = msg["text"]
                concat_msg = message
                while concatenate and message and len(message) > 150:
                    time.sleep(10)
                    message = None
                    msg = self.read_next_message(
                        all_msg=all_msg,
                        delete=delete,
                        tuple=tuple,
                        concatenate=concatenate
                    )
                    if msg:
                        try:
                            message = msg
                            concat_msg += message
                        except Exception:
                            (_, _, _, message) = msg
                            concat_msg += message
                delete_messages(to_delete)
                if tuple:
                    return produce_tuple(concat_msg)
                return concat_msg
            if not msg_is_multipart(msg):
                logging.error("SIM800L - missing text in non PDU message: %s", msg)
        return None

    def command(
        self,
        cmdstr, lines=-1, waitfor=0, msgtext=None, msgpdu=None,
        flush_input=True, timeout=3
    ):
        """
        Executes an AT command
        :param cmdstr: AT command string
        :param msgtext: SMS text; to be used in case of SMS message command
        :param msgpdu: PDU SMS; to be used in case of SMS message command
        :param flush_input: True if residual input is flushed before sending
            the command. False disables flushing.
        :return: returned data (string):
            "OK", "ERROR", "", string (all lines before OK)
        """
        response = ''
        while self.ser.in_waiting and flush_input:
            flush = self.check_incoming()
            logging.debug("SIM800L - Flushing %s", flush)
        logging.log(
            5,  # VERBOSE
            "SIM800L - Writing '%s'",
            repr(cmdstr)
        )
        try:
            self.ser.write(cmdstr.encode())
        except Exception as e:
            logging.error("SIM800L - command write error: %s", e)
            return "ERROR"
        if msgpdu or msgtext:
            buf = self.ser.read(4)
            if not buf or b'>' not in buf:
                line = self.ser.readline()
                buf += line
                if not buf or b'>' not in buf:
                    start_time = time.time()
                    while True:
                        flush = self.check_incoming()
                        if flush == ('GENERIC', '>'):
                            break
                        if time.time() - start_time > timeout:
                            self.ser.write(b'\x1A' + b'\x0A')
                            flush = self.check_incoming()
                            logging.error(
                                "SIM800L - Chevron not received in time: '%s'",
                                flush
                            )
                            return "ERROR"
            if not buf or b'>' not in buf:
                start_time = time.time()
                while True:
                    flush = self.check_incoming()
                    if flush == ('GENERIC', '>'):
                        break
                    if time.time() - start_time > timeout:
                        self.ser.write(b'\x1A' + b'\x0A')
                        flush = self.check_incoming()
                        logging.error(
                            "SIM800L - Chevron not received in time: '%s'", flush
                        )
                        return "ERROR"
        if msgpdu:
            try:
                self.ser.write(msgpdu + b'\x1A' + b'\x0A')
            except Exception as e:
                logging.error("SIM800L - command msgpdu write error: %s", e)
                return "ERROR"
        if msgtext:
            try:
                self.ser.write(convert_gsm(msgtext) + b'\x1A' + b'\x0A')
            except Exception as e:
                logging.error("SIM800L - command msgtext write error: %s", e)
                return "ERROR"
        if waitfor > 1000:  # this is kept from the original code...
            time.sleep((waitfor - 1000) / 1000)

        start_time = time.time()
        while True:
            if lines == 0:
                logging.log(5, "SIM800L - end of sim800l.command()")
                return response
            buf = self.ser.readline().strip()  # discard linefeed etc
            if not buf:
                if time.time() - start_time > timeout:
                    break
                continue
            line = convert_to_string(buf)
            if not line:
                continue
            if lines > 0:
                lines -= 1
            start_time = time.time()
            if line.startswith('+CMTI: "SM",'):
                logging.debug("SIM800L - New message received '%s'", buf)
                continue
            if line == "OK":
                if msgpdu or msgtext:
                    return 'OK'
                if response:
                    logging.log(
                        5, "SIM800L - sim800l.command() got positive answer %s",
                        repr(response)
                    )
                    return response
                else:
                    logging.log(5, "SIM800L - sim800l.command() got %s", line)
                    return 'OK'
            if line.startswith("ERROR"):
                if response:
                    logging.warning(
                        "SIM800L - sim800l.command() error: got %s and %s",
                        repr(line), repr(response)
                    )
                else:
                    logging.log(
                        5, "SIM800L - sim800l.command() ERROR (got %s)", line
                    )
                return "ERROR"
            response += line + '\n'
        logging.log(  # VERBOSE
            5, "SIM800L - command() returning %s", repr(response)
        )
        return response

    def command_ok(
        self,
        cmd,
        check_download=False,
        check_error=False,
        cmd_timeout=10,
        attempts=2
    ):
        """
        Send AT command to the device and check that the return sting is OK
        :param cmd: AT command
        :param check_download: True if the "DOWNLOAD" return sting has to be
                                checked
        :param check_error: True if the "ERROR" return sting has to be checked
        :param cmd_timeout: timeout in seconds
        :param attempts: number of attempts before returning False
        :return: True = OK received, False = OK not received. If check_error,
                    can return "ERROR"; if check_download, can return "DOWNLOAD"
        """
        logging.debug("SIM800L - Sending command '%s'", cmd)
        r = self.command(cmd + "\n", timeout=cmd_timeout)
        while attempts:
            if not r:
                r = ""
            if r.strip() == "OK":
                return True
            if check_download and r.strip() == "DOWNLOAD":
                return "DOWNLOAD"
            if check_error and r.strip() == "ERROR":
                return "ERROR"
            if not r:
                expire = time.monotonic() + cmd_timeout
                s = self.check_incoming()
                while (s[0] == 'GENERIC' and
                        not s[1] and
                        time.monotonic() < expire):
                    time.sleep(0.1)
                    s = self.check_incoming()
                if s == ("OK", None):
                    return True
                if check_download and s == ("DOWNLOAD", None):
                    return "DOWNLOAD"
                if check_error and s == ("ERROR", None):
                    return "ERROR"
            attempts -= 1
            time.sleep(ATTEMPT_DELAY)
        logging.critical(
            "SIM800L - Missing 'OK' return message after: '%s': '%s'", cmd, r)
        return False

    def command_data_ok(self,
                   cmd,
                   attempts=2):
        """
        Send AT command to the device, read the answer and then check the
        existence of the OK message. "cmd" shall not have the ending newline.
        :param cmd: AT command
        :param attempts: number of attempts before returning None or False
        :return: string in case of successful retrieval; otherwise None
            if module error or False if missing OK message
        """
        while attempts:
            answer = self.command(cmd + '\n')
            if not answer:
                if attempts > 1:
                    attempts -= 1
                    continue
                return None
            if answer != 'OK':
                logging.log(
                    5,
                    "SIM800L - sim800l.command_data_ok() - returned data: %s",
                    answer.strip()
                )
                return answer.strip()
            r = self.check_incoming()
            if r != ("OK", None):
                if attempts > 1:
                    attempts -= 1
                    continue
                logging.error(
                    "SIM800L - wrong '" + cmd + "' return message: %s", r
                )
                return False
            return answer

    def check_incoming(self):
        """
        Check incoming data from the module, decoding messages
        :return: tuple
        """
        buf = None
        if self.ser.in_waiting:
            buf = self.ser.readline()
            buf = convert_to_string(buf)
            while buf.strip() == "" and self.ser.in_waiting:
                buf = self.ser.readline()
                buf = convert_to_string(buf)
                logging.debug("SIM800L - read line: '%s'", buf)
            return self.decode_cmd_response(buf)
        return "GENERIC", buf

    def decode_cmd_response(self, buf):
        if not buf:
            return "GENERIC", buf
        params = buf.rstrip().split(',')

        # +HTTPACTION (HTTP GET and POST methods)
        if (len(params) == 3 and len(params[0]) == 14 and
                params[0].startswith("+HTTPACTION: ")):
            try:
                method = httpaction_method[params[0][-1]]
            except KeyError:
                method = httpaction_method['X']
            try:
                error_message = httpaction_status_codes[params[1]]
            except KeyError:
                error_message = httpaction_status_codes['000']
            if not params[2].strip().isnumeric():
                return "HTTPACTION_" + method, False, 0
            try:
                return "HTTPACTION_" + method, int(params[1]), int(params[2])
            except Exception as e:
                logging.error("Invalid +HTTPACTION: %s", buf)
            return "HTTPACTION_" + method, None, None

        # +COPN (Read Operator Names)
        elif params[0].startswith("+COPN: "):
            numeric = params[0].split(':')[1].strip().replace('"', "")
            name = params[1].strip().replace('"', "").strip()
            return "COPN", numeric, name

        # +CFUN (Read Phone functionality indication)
        elif params[0].startswith("+CFUN: "):
            numeric = params[0].split(':')[1].strip()
            if numeric == "0":
                logging.debug(
                    "SIM800L - CFUN - Minimum functionality.")
            if numeric == "1":
                logging.debug(
                    "SIM800L - CFUN - Full functionality (Default).")
            if numeric == "4":
                logging.debug(
                    "SIM800L - CFUN - Disable phone both transmit"
                    " and receive RF circuits.")
            return "CFUN", numeric

        # +CPIN (Read PIN)
        elif params[0].startswith("+CPIN: "):
            pin = params[0].split(':')[1].strip()
            return "PIN", pin

        # Call Ready
        elif params[0] == "Call Ready":
            logging.warning("SIM800L - device call ready after reset")
            return "MSG", params[0]

        # +CTZV Network time zone
        elif params[0].startswith("+CTZV: "):
            logging.warning("SIM800L - Network time zone: %s", params[0])
            return "CTZV", params[0]

        # *PSUTTZ Network date, time and time zone
        elif params[0].startswith("*PSUTTZ: "):
            logging.warning(
                "SIM800L - Network date, time and time zone: %s", params[0]
            )
            return "PSUTTZ", params[0]

        # DST Network date, time and time zone
        elif params[0].startswith("DST: "):
            logging.warning(
                "SIM800L - Daylight saving time: %s", params[0]
            )
            return "DST", params[0]

        # +CIEV Network Operator data
        elif params[0].startswith("+CIEV: "):
            logging.warning(
                "SIM800L - Network Operator data: %s", params[0]
            )
            return "CIEV", params[0]

        # SMS Ready
        elif params[0] == "SMS Ready":
            logging.warning("SIM800L - device SMS ready after reset")
            return "MSG", params[0]

        # +CREG (Read Registration status)
        elif params[0].startswith("+CREG: "):
            numeric = params[0].split(':')[1].strip()
            if numeric == "0":
                logging.debug(
                    "SIM800L - CREG - Not registered, not searching.")
            if numeric == "1":
                logging.debug(
                    "SIM800L - CREG - Registered, home network.")
            if numeric == "2":
                logging.debug(
                    "SIM800L - CREG - Not registered, searching.")
            if numeric == "3":
                logging.debug(
                    "SIM800L - CREG - Registration denied.")
            if numeric == "4":
                logging.debug(
                    "SIM800L - CREG - Unknown.")
            if numeric == "5":
                logging.debug(
                    "SIM800L - CREG - Registered, roaming.")
            return "CREG", numeric

        # +CTZV (Read Time Zone)
        elif params[0].startswith("+CTZV: "):
            tz1 = params[0].split(':')[1].strip()
            tz2 = params[1].strip()
            return "CTZV", tz1, tz2

        # *PSUTTZ (Refresh time and time zone by network.)
        elif params[0].startswith("*PSUTTZ: "):
            year = params[0].split(':')[1].strip()
            month = params[1].strip()
            day = params[2].strip()
            hour = params[3].strip()
            minute = params[4].strip()
            second = params[5].strip()
            tz1 = params[6].strip().replace('"', "")
            tz2 = params[7].strip()
            return (
                "PSUTTZ", year, month, day, hour, minute, second, tz1, tz2)

        # DST (Read Network Daylight Saving Time)
        elif params[0].startswith("DST: "):
            dst = params[0].split(':')[1].strip()
            return "DST", dst

        # RDY (Power procedure completed)
        elif params[0] == "RDY":
            return "RDY", None

        # +SAPBR (IP address)
        elif params[0].startswith("+SAPBR: "):
            ip_address = params[2].replace('"', "").strip()
            if (params[0].split(':')[1].strip() == "1" and
                    params[1].strip() == "1"):
                return "IP", ip_address
            return "IP", None

        # +CMTI (legacy code, partially revised) fires callback_msg()
        elif params[0].startswith("+CMTI"):
            self._msgid = int(params[1])
            if self.msg_action:
                self.msg_action(int(params[1]))
            return "CMTI", self._msgid

        elif params[0].startswith("+CMGS"):
            logging.warning("SIM800L - New message delivered '%s'", params)

        elif params[0].startswith("+CUSD"):
            logging.warning(
                "SIM800L - USSD response from the network, or network initiated operation '%s'",
                params
            )

        # ERROR
        elif params[0] == "ERROR":
            return "ERROR", None

        # NO CARRIER (legacy code, partially revised) fires callback_no_carrier()
        elif params[0] == "NO CARRIER":
            if self.no_carrier_action:
                self.no_carrier_action()
            return "NOCARRIER", None

        # +CDNSGIP (DNS query)
        elif params[0].startswith('+CDNSGIP: '):
            if params[0].split(':')[1].strip() != '1':
                if params[1] == '8':
                    return "DNS", None, "DNS_COMMON_ERROR"
                elif params[1] == '3':
                    return "DNS", None, "DNS_NETWORK_ERROR"
                else:
                    return "DNS", None, "DNS_UNKNOWN_ERROR" + params[1]
            dns = params[2].replace('"', '').strip()
            logging.info("SIM800L - DNS: %s", dns)
            if len(params) > 3:
                return "DNS", dns, params[3].replace('"', '').strip()
            else:
                return "DNS", dns, params[1].replace('"', '').strip()

        # +CNTP (NTP sync)
        elif params[0].startswith('+CNTP: '):
            if params[0] == '+CNTP: 1':
                logging.debug("SIM800L - Network time sync successful")
                return "NTP", self.get_date(), 0
            elif params[0] == '+CNTP: 61':
                logging.error("SIM800L - Sync time network error")
                return "NTP", None, 61
            elif params[0] == '+CNTP: 62':
                logging.error("SIM800L - Sync time DNS resolution error")
                return "NTP", None, 62
            elif params[0] == '+CNTP: 63':
                logging.error("SIM800L - Sync time connection error")
                return "NTP", None, 63
            elif params[0] == '+CNTP: 64':
                logging.error("SIM800L - Sync time service response error")
                return "NTP", None, 64
            elif params[0] == '+CNTP: 65':
                logging.error(
                    "SIM800L - Sync time service response timeout")
                return "NTP", None, 65
            else:
                logging.error(
                    "SIM800L - Sync time service - Unknown error code '%s'",
                    params[0])
                return "NTP", None, 1

        # RING
        elif params[0] == "RING":  # The DCE has detected an incoming call signal from network
            if self.incoming_action:
                self.incoming_action()
            # @todo handle
            return "RING", None

        # +CLIP - incoming voice call is detected
        elif params[0].startswith("+CLIP"):
            number = params[0].split(": ")[-1].replace('"', "")
            if self.clip_action:
                self.clip_action(number)
            return "CLIP", number

        # OK
        elif buf.strip() == "OK":
            return "OK", None

        # DOWNLOAD
        elif buf.strip() == "DOWNLOAD":
            return "DOWNLOAD", None

        return "GENERIC", buf
