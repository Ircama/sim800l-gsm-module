# Raspberry Pi SIM800L GSM module

[![PyPI](https://img.shields.io/pypi/v/sim800l-gsm-module.svg?maxAge=2592000)](https://pypi.org/project/sim800l-gsm-module)
[![Python Versions](https://img.shields.io/pypi/pyversions/sim800l-gsm-module.svg)](https://pypi.org/project/sim800l-gsm-module/)
[![PyPI download month](https://img.shields.io/pypi/dm/sim800l-gsm-module.svg)](https://pypi.python.org/pypi/sim800l-gsm-module/)
[![GitHub license](https://img.shields.io/badge/license-CC--BY--NC--SA--4.0-blue)](https://raw.githubusercontent.com/Ircama/raspberry-pi-sim800l-gsm-module/master/LICENSE)

[SIM800L GSM module](https://www.simcom.com/product/SIM800.html) library for Linux systems like the Raspberry Pi.

This library interfaces the SIM800L GSM device and allows sending, receiving and deleting SMS messages, as well as performing HTTP GET/POST requests, synching/updating the RTC and getting other information from the module.

## Setup

## Hw Requirements
- Linux system with a UART serial port, or Raspberry Pi with [Raspberry Pi OS](https://en.wikipedia.org/wiki/Raspberry_Pi_OS) (this library has been tested with Buster and Bullseye).
- External power supply for the SIM800L (using the Raspberry Pi 5V power supply, a standard diode (1N4007) with voltage drop of about 0.6 volts and a 2200 uF capacitor might work).

### Installation

Check that the [Python](https://www.python.org/) version is 3.6 or higher (`python3 -V`), then install the *sim800l-gsm-module* with the following command:

```shell
python3 -m pip install sim800l-gsm-module
```

Prerequisite components: *pyserial*, *gsm0338*. All needed prerequisites are automatically installed with the package.

Alternatively to the above mentioned installation method, the following steps allow installing the latest version from GitHub.

- Optional preliminary configuration (if not already done):

  ```shell
  sudo apt-get update
  sudo apt-get -y upgrade
  sudo add-apt-repository universe # this is only needed if "sudo apt install python3-pip" fails
  sudo apt-get update
  sudo apt install -y python3-pip
  python3 -m pip install --upgrade pip
  sudo apt install -y git
  ```

- Run this command:

```shell
  python3 -m pip install git+https://github.com/Ircama/raspberry-pi-sim800l-gsm-module
```

To uninstall:

```shell
python3 -m pip uninstall -y sim800l-gsm-module
```

### Hardware connection

![sim800l](https://user-images.githubusercontent.com/8292987/155906146-e6c934e1-34b1-4499-9efe-c497f54d88f3.jpg)

### Disabling the serial console login

Disabling the serial console login is needed in order to enable communication between the Raspberry Pi and SIM800L via /dev/serial0.

- Open the terminal on your pi and run `sudo raspi-config` 
- Select Interfaces → Serial 
- Select No to the 1st prompt and Yes for the 2nd one.

## Basic use

Check [Usage examples](#usage-examples). Basic program:

```python 
from sim800l import SIM800L
sim800l = SIM800L()
sim800l.setup()
print("Unit Name:", sim800l.get_unit_name())
```

## API Documentation

Tested with SIM800L firmware Revision:[1418B05SIM800L24](https://github.com/geekmatic/SIM800_firmware_updates) (SIM800L R14.18, Build 05).

SIM800 does not support AT+HTTPSSL on firmware release <R14.00 (e.g., 1308B08SIM800L16 -> SIM800L R13.08 Build 08).

For debugging needs, logs can be set to the maximum level (verbose mode, tracing each request/response) with the following command:

```python
import logging
logging.getLogger().setLevel(5)`
```

---

#### `sim800l = SIM800L(port='/dev/serial0', baudrate=115000, timeout=3.0)`
Class instantiation (using [pySerial](https://github.com/pyserial/pyserial))
- `port`: port name
- `baudrate`: baudrate in bps
- `timeout`: timeout in seconds

---

#### `check_sim()`
Check whether the SIM card has been inserted.
 *return*: `True` if the SIM is inserted, otherwise `False`. `None` in case of module error.

---

#### `command(cmdstr, lines=1, waitfor=500, msgtext=None, flush_input=True)`
Executes an AT command. A newline must be added at the end of the AT command (e.g., `sim800l.command("AT+CCLK?\n", lines=-1)`).
Input is flushed before sending the command (`flush_input=False` disables flushing).
The first newline is discarded (if `lines` != 0).
- `cmdstr`: AT command string
- `lines`: number of expexted lines (see below)
- `waitfor`: number of (milliseconds - 1000) to wait for the returned data; not used if <= 1000 milliseconds.
- `msgtext`: only to be used when sending SMS messages, it includes the SMS text.
- `flush_input`: `True` if residual input is flushed before sending the command. `False` disables flushing.

 *return*: the first line is returned (string); use `check_incoming()` to read the subsequent lines. `None` is returned when no data is received (or module error).

If `lines=0`, terminates just after writing text to the device (no bytes read; no return code, e.g. `None` returned). Note: `check_incoming()` can be subsequently used to read data from the device (see subsequent example).

If `lines`<0 (e.g., `lines=-1`), return the concatenation of all read lines (until pySerial timeout `sim800l.serial_port().timeout`), separating each line by a linefeed.

If `lines`>1 (legacy code), return the concatenation of all read lines, separating each line by a linefeed, discarding null lines and "OK".

Example:

```python
import time
from sim800l import SIM800L

sim800l=SIM800L('/dev/serial0')

# Send data and return the first line
print(sim800l.command("AT+CCLK?\n"))  # ...+CCLK...

# Same as before, but reading both lines
sim800l.command("AT+CCLK?\n", lines=0)  # send AT command without reading data
print("First read line:", sim800l.check_incoming())  # ...+CCLK...
print("Second read line:", sim800l.check_incoming())  # ...'OK'...

# Same as before, but more elaborated
sim800l.command("AT+CCLK?\n", lines=0)
expire = time.monotonic() + 2  # seconds
sequence = ""
s = sim800l.check_incoming()
date = None
while time.monotonic() < expire:
    if s[0] == 'GENERIC' and s[1] and s[1].startswith('+CCLK: "'):
        date = s[1].split('"')[1]
        sequence += "D"
    if s == ('OK', None):
        sequence += "O"
    if sequence == "DO":
        print("Date:", date)
        break
    time.sleep(0.1)
    s = sim800l.check_incoming()

if not date:
    print("Error")
```

---

#### `command_data_ok(cmd, attempts=2)`
Send AT command to the device, read the answer and then check the
existence of the OK message. "cmd" shall not have the ending newline.
- `cmd`: AT command
- `attempts`: number of attempts before returning None or False
 *return*: string in case of successful retrieval; otherwise None if module error or False if missing OK message

---

#### `command_ok(cmd, check_download=False, check_error=False, cmd_timeout=10, attempts=2)`
Send AT command to the device and check that the return sting is OK.
Newline must not be put at the end of the string.
- `cmd`: AT command
- `check_download`: `True` if the “DOWNLOAD” return sting has to be checked
- `check_error`: `True` if the “ERROR” return sting has to be checked
- `cmd_timeout`: timeout in seconds
- `attempts`: number of attempts before returning False
 *return*: `True` = OK received, `False` = OK not received (or module error). If check_error, can return `ERROR`; if check_download, can return `DOWNLOAD`

---

#### `connect_gprs(apn=None)`
Connect to the bearer and get the IP address of the PDP context.
Automatically perform the full PDP context setup.
Reuse the IP session if an IP address is found active.
- `apn`: APN name
 *return*: `False` if error (including module error), otherwise return the IP address (as string)

---

#### `delete_sms(index_id)`
Delete the SMS message referred to the index
- `index_id`: index in the SMS message list starting from 1
 *return*: `None`

---

#### `disconnect_gprs(apn=None)`
Disconnect the bearer.
 *return*: `True` if succesfull, `False` if error

---

#### `get_battery_voltage()`
Return the battery voltage in Volts
 *return*: floating (volts). `None` in case of module error.

Example: 4.158

---

#### `get_ccid()`
Get the ICCID
 *return*: string; `None` in case of module error.

Example: "1122334455667788990f"

---

#### `get_date()`
Return the clock date available in the module.
 *return*: `datetime.datetime`; `None` in case of module error.

Example: "2022-03-09 19:59:31"

---

#### `get_flash_id()`
Get the SIM800 GSM module flash ID
 *return*: string; `None` in case of module error.

Example: "Device Name:SERIAL§FLASH§MTKSIP§6261§SF§24§01"

---

#### `get_hw_revision()`
Get the SIM800 GSM module hw revision
 *return*: string; `None` in case of module error.

Example: "Revision:1418B05SIM800L24"

---

#### `get_imsi()`
Get the IMSI
 *return*: string; `None` in case of module error.

Example: "112233445566778"

---

#### `get_ip()`
Get the IP address of the PDP context
 *return*: valid IP address string if the bearer is connected, otherwise `None` (e.g., module error).

---

#### `get_msgid()`
Return the unsolicited notification of incoming SMS
 *return*: number

---

#### `get_msisdn()`
Get the MSISDN subscriber number
 *return*: string. `None` in case of module error.

---

#### `get_operator()`
Display the current network operator that the handset is currently
registered with.
 *return*: operator string. `None` in case of module error. `False` in case of SIM error.

Example: "Vodafone"

---

#### `get_operator_list()`
Display a full list of network operator names.
 *return*: dictionary of "numeric: "name" fields; None in case of error.

---

#### `get_serial_number()`
Get the SIM800 GSM module serial number
 *return*: string; `None` in case of module error.

Example: "866782042319455"

---

#### `get_service_provider()`
Get the Get Service Provider Name stored inside the SIM
 *return*: string. `None` in case of module error. `False` in case of SIM error.

---

#### `get_signal_strength()`
Get the signal strength
 *return*: number; min = 3, max = 100; `None` in case of module error.

Example: 40.625

---

#### `get_temperature()`
Get the SIM800 GSM module temperature in Celsius degrees
 *return*: string; `None` in case of module error.

Example: "24.21"

---

#### `get_unit_name()`
Get the SIM800 GSM module unit name
 *return*: string (e.g., "SIM800 R14.18"); `None` in case of module error.

---

#### `hard_reset(reset_gpio)`
Perform a hard reset of the SIM800 module through the RESET pin.
This function can only be used on a Raspberry Pi.
- `reset_gpio`: RESET pin
 *return*: `True` if the SIM is active after the reset, otherwise `False`. `None` in case of module error.

---

#### `http(url="...", data="...", apn="...", method="...", use_ssl=False, ua=None, content_type="application/json", allow_redirection=False, http_timeout=10, keep_session=False, attempts=2)`
Run the HTTP GET method or the HTTP PUT method and return retrieved data
Automatically perform the full PDP context setup and close it at the end
(use keep_session=True to keep the IP session active). Reuse the IP
session if an IP address is found active.
Automatically open and close the HTTP session, resetting errors.
- `url`: URL
- `data`: input data used for the PUT method (bytes; e.g., use `data="string".encode()`)
- `apn`: APN name
- `method`: "GET" or "PUT"
- `use_ssl`: `True` if using HTTPS, `False` if using HTTP (see note)
- `ua`: User agent (string); is not set, the SIM800L default user agent is used ("SIMCOM_MODULE").
- `content_type`: (string) set the "Content-Type" field in the HTTP header
- `allow_redirection`: `True` if HTTP redirection is allowed (e.g., if the server sends a redirect code (range 30x), the client will automatically send a new HTTP request)
- `http_timeout`: timeout in seconds
- `keep_session`: `True` to keep the PDP context active at the end
- `attempts`: number of attempts before returning False
 *return*: `False` if error, otherwise the returned data (as string)

While the *Content type* header field can be set, the *Content encoding* is always null.

Sending data with [zlib](https://docs.python.org/3/library/zlib.html) is allowed:

```python
import zlib
body = zlib.compress('hello world'.encode())
sim800l.http("...url...", method="PUT", content_type="zipped", data=body, apn="...")
```

[Note on SSL](https://github.com/ostaquet/Arduino-SIM800L-driver/issues/33#issuecomment-761763635): SIM800L datasheets report that the embedded IP stack only supports SSL2, SSL3 and TLS 1.0. These cryptographic protocols are deprecated for all modern backend servers and the connection will be generally denied by the server, typically leading to SIM800L error 605 or 606 when establishing an HTTPS connection. Some SIM800L datasheets also report support of TLS 1.2 but this does not appear to be true with firmware Revision 1418B05SIM800L24.  So, using `use_ssl=True` is discouraged; setting a Python web server to support the SSL option of a SIM800L client module is not straightforward (it is better to use an [application encryption](https://stackoverflow.com/a/55147077/10598800) instead of SSL). Generally, to be able to connect an HTTPS web service, a separate proxy server is needed (e.g., a custom Python application in cloud), receiving non-SSL HTTP requests from the SIM800L module (possibly with application encryption) and forwarding them to the AWS Lambda HTTP API gateway via HTTPS.

Notice also that, depending on the web server, a specific SSL certificate could be needed for a successful HTTPS connection; the SIM800L module has a limited support of SSL certificates and [installing an additional one](https://stackoverflow.com/questions/36996479/how-sim800-get-ssl-certificate
) is not straightforfard.

An additional problem is related to possible DNS errors when accessing endpoints. Using IP addresses is preferred.

---

#### `internet_sync_time(time_server='193.204.114.232', time_zone_quarter=4, apn=None, http_timeout=10, keep_session=False)`
Connect to the bearer, get the IP address and sync the internal RTC with
the local time returned by the NTP time server (Network Time Protocol).
Automatically perform the full PDP context setup.
Disconnect the bearer at the end (unless keep_session = `True`)
Reuse the IP session if an IP address is found active.
- `time_server`: internet time server (IP address string)
- `time_zone_quarter`: time zone in quarter of hour
- `http_timeout`: timeout in seconds
- `keep_session`: `True` to keep the PDP context active at the end
 *return*: `False` if error, otherwise the returned date (`datetime.datetime`)

Example: "2022-03-09 20:38:09"

---

#### `query_ip_address(url=None, apn=None, http_timeout=10, keep_session=False)`
Connect to the bearer, get the IP address and query an internet domain
name, getting the IP address.
Automatically perform the full PDP context setup.
Disconnect the bearer at the end (unless keep_session = `True`)
Reuse the IP session if an IP address is found active.
- `url`: internet domain name to be queried
- `http_timeout`: timeout in seconds
- `keep_session`: True to keep the PDP context active at the end
 *return*: `False` if error (`None` for module error), otherwise the returned IP address (string)

---

#### `is_registered()`
Check whether the SIM is Registered, home network
 *return*: Truse if registered, otherwise `False`. . `None` in case of module error.

---

#### `read_and_delete_all(index_id=1)`
Read the message at position 1, otherwise delete all SMS messages, regardless the type (read, unread, sent, unsent, received).
If the message is succesfully retrieved, no deletion is done. (Deletion only occurs in case of retrieval error.)
Notice that, while generally message 1 is the first to be read, it might happen that no message at position 1 is available,
while other positions might still include messages; for those cases (missing message at position 1, but other messages
available at other positions), the whole set of messages is deleted.
Use `index_id=0` to delete all messages without trying to retrieve the one at position 1.
 *return*: text of the read message

---

#### `read_next_message(all_msg=False)`
Check messages, read one message and then delete it. This function can be repeatedly called to read all stored/received messages one by one and delete them.
- `all_msg`: `True` if no filter is used (read and unread messages).  Otherwise only the unread messages are returned.
 *return*: retrieved message text (string), otherwise: `None` = no messages to read; `False` = read error (module error)

---

#### `read_sms(index_id)`
Read the SMS message referred to the index_id position
- `index_id`: index in the SMS message list starting from 1
 *return*: `None` if error, otherwise return a tuple including: MSISDN origin number, SMS date string, SMS time string, SMS text

---

#### `send_sms(destno, msgtext)`
Send SMS message
- `destno`: MSISDN destination number
- `msgtext`: Text message
 *return*: `True` if message is sent, otherwise `False`

---

#### `serial_port()`
Return the serial port (for direct debugging)
 *return*:

---

#### `set_date()`
Set the Linux system date with the GSM time
 *return*: date string. `None` in case of module error.

Example: "2022-03-09 20:10:54"

---

#### `setup()`
Run setup strings for the initial configuration of the SIM800 module
 *return*: `True` if setup is successfully completed; `None` in case of module error.

---

#### `sim800l.convert_gsm(string)`
Encode `string` to bytes using the 3GPP TS 23.038 / ETSI GSM 03.38 codec.
- `string`: UTF8 string
 *return*: gsm03.38 bytes

---

#### `sim800l.convert_to_string(buf)`
Decode GSM 03.38 encoded bytes, returning a string.
- `buf`: gsm03.38 bytes
 *return*: UTF8 string

---

#### `check_incoming()`
Internal function, used to check incoming data from the SIM800L module, decoding messages.
It also fires the functions configured with `callback_msg()` and `callback_no_carrier()`.
 *return*: tuple

Return values:
- `('GENERIC', None)`: no data received
- `('GENERIC', data)`: received data is returned (`data` is a string)
- `("HTTPACTION_PUT", False, size)`: invalid HTTP PUT method, with return code different from 200
- `("HTTPACTION_PUT", True, size)`: valid HTTP PUT method; `size` is the number of returned characters
- `("HTTPACTION_GET", False, size)`: invalid HTTP GET method, with return code different from 200
- `("HTTPACTION_GET", True, size)`: valid HTTP GET method; `size` is the number of returned characters
- `("IP", "ip address")`: bearer connected, received IP address
- `("IP", None)`: Disconnected
- `("CMTI", index_id)`: received SMS message with index `index_id`
- `("NOCARRIER", None)`: "NO CARRIER" message detected
- `("RING", None)`: "RING" message detected
- `("OK", None)`: "OK" message detected
- `("DOWNLOAD", None)`: "DOWNLOAD" message detected
- `("ERROR", None)`: "ERROR" message detected
- `("DNS", None, error)`: DNS error message
- `("DNS", dns1, dns2)`: IP address and FQDN retrieved from the DNS
- `("NTP", None, error)`: NTP query error
- `("NTP", date, 0)`: Successful NTP query; `date` is `datetime.datetime` format
- `("COPN", numeric, name)`: Operator number and name
- `("CREG", numeric)`: Registration status
- `("CTZV", tz1, tz2)`: Time Zone
- `("PSUTTZ", year, month, day, hour, minute, second, tz1, tz2)`: time and time zone
- `("DST", dst)`: Daylight Saving Time
- `("RDY", None)`: Power procedure completed
- `("CFUN", numeric)`: Phone functionality indication
- `("PIN", pin)`: PIN
- `("MSG", "Call Ready)`: Call ready
- `("MSG", "SMS Ready)`: SMS ready

Usage sample 1:
```python
if self.check_incoming() != ("OK", None):
    print("Error")
```

---

#### `get_clip()`
(legacy code, not used)

---

#### `set_charset_hex()`
Set the module to the HEX character set (only hexadecimal values from 00 to FF)
 *return*: "OK" if successful, otherwise `None` in case of module error.

---

#### `set_charset_ira()`
Set the module to the International reference alphabet (ITU-T T.50) character set
 *return*: "OK" if successful, otherwise `None` in case of module error.

---

#### `callback_incoming(function)`
(legacy code, not used)
- `function`: Python function with no args

---

#### `callback_msg(function)`
(legacy code)
Configure a callback function, fired when `check_incoming()` receives a message (`+CMTI` returned, indicating new message received).
- `function`: Python function with no args

---

#### `callback_no_carrier(function)`
(legacy code)
Configure a callback function, fired when `check_incoming()` receives "NO CARRIER".
- `function`: Python function with no args

---

## Usage examples

```python 
from sim800l import SIM800L
sim800l = SIM800L('/dev/serial0')
```

#### Return module information
```python
from sim800l import SIM800L

sim800l = SIM800L()
sim800l.setup()

print("Date:",
    sim800l.get_date())
print("Operator:",
    sim800l.get_operator())
print("Service provider:",
    sim800l.get_service_provider())
print("Signal strength:",
    sim800l.get_signal_strength(), "%")
print("Temperature:",
    sim800l.get_temperature(), "degrees")
print("MSISDN:",
    sim800l.get_msisdn())
print("Battery Voltage:",
    sim800l.get_battery_voltage(), "V")
print("IMSI:",
    sim800l.get_imsi())
print("ICCID:",
    sim800l.get_ccid())
print("Unit Name:",
    sim800l.get_unit_name())

if sim800l.is_registered():
    print("SIM is registered.")
else:
    print("SIM NOT registered.")
```

#### Sync time with internet
```python
sim800l.internet_sync_time(apn="...", time_zone_quarter=...)
```

#### Query the DNS for an internet name
```python
sim800l.query_ip_address(url="httpbin.org", apn="...")
```

#### Hard reset
```python
# Note: connect the RST pin with GPIO23 (pin 16 of the Raspberry Pi)
sim800l.hard_reset(23)  # see schematics
```

#### Send SMS
```python
sms="Hello there"
#sim800l.send_sms(dest.no,sms)
sim800l.send_sms('2547xxxxxxxx',sms)
```

#### Read the next SMS message
```python
msg = sim800l.read_next_message(all_msg=True)
```

#### HTTP GET samples
```python
print(sim800l.http("httpbin.org/ip", method="GET", apn="..."))
print(sim800l.http("httpbin.org/get", method="GET", use_ssl=False, apn="..."))  # HTTP
print(sim800l.http("httpbin.org/get", method="GET", use_ssl=True, apn="..."))  # HTTPS
```

Note: time ago `httpbin.org` succeeded with HTTPS because supporting an old SSL version. Curently the test fails with HTTPS.

#### HTTP PUT sample
```python
print(sim800l.http("httpbin.org/post", data='{"name","abc"}'.encode(), method="PUT", apn="..."))  # HTTPS
print(sim800l.http("httpbin.org/post", data='{"name","abc"}'.encode(), method="PUT", use_ssl=False, apn="..."))  # HTTP
```

#### Read the n-th SMS
```python
Read the SMS indexed by the index_id value [ref. also check_incoming()]
index_id=...  # e.g., 1
sim800l.read_sms(index_id)
```

#### Callback action
(legacy code)
```python
def print_delete():
    # Assuming the SIM has no SMS initially
    sms = sim800l.read_sms(1)
    print(sms)
    sim800l.delete_sms(1)

sim800l.callback_msg(print_delete)

while `True`:
    sim800l.check_incoming()
```

## References
- [AT Datasheet](https://microchip.ua/simcom/2G/SIM800%20Series_AT%20Command%20Manual_V1.12.pdf)
- [Application notes](https://www.microchip.ua/simcom/?link=/2G/Application%20Notes)
- [Specifications](https://simcom.ee/documents/?dir=SIM800L)

Arduino:
- https://github.com/vshymanskyy/TinyGSM
- https://lastminuteengineers.com/sim800l-gsm-module-arduino-tutorial/

## History
This library is a fork of https://github.com/jakhax/raspberry-pi-sim800l-gsm-module with many additions.

The backward compatibility with the original repo is still kept.

> SIM900/SIM800 are 2G only modems, make sure your provider supports 2G as it is already being phased out in a lot of areas around the world, else a 3G/4G modem like the SIM7100 / SIM5300 is warranted.  
