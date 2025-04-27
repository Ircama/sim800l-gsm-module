# Raspberry Pi SIM800L, SIM800C and SIM800H GSM module

[![PyPI](https://img.shields.io/pypi/v/sim800l-gsm-module.svg?maxAge=2592000)](https://pypi.org/project/sim800l-gsm-module)
[![Python Versions](https://img.shields.io/pypi/pyversions/sim800l-gsm-module.svg)](https://pypi.org/project/sim800l-gsm-module/)
[![PyPI download month](https://img.shields.io/pypi/dm/sim800l-gsm-module.svg)](https://pypi.python.org/pypi/sim800l-gsm-module/)
[![GitHub license](https://img.shields.io/badge/license-CC--BY--NC--SA--4.0-blue)](https://raw.githubusercontent.com/Ircama/raspberry-pi-sim800l-gsm-module/master/LICENSE)

[SIM800L GSM module](https://www.simcom.com/product/SIM800.html) library for Linux systems like the Raspberry Pi. This library was also successfully tested with SIM800C and should also support SIM800H.

This library driver interfaces with the SIM800L, SIM800C and SIM800H GSM module using AT commands over a serial connection. It allows sending, receiving and deleting SMS messages, as well as performing HTTP GET/POST requests, synching/updating the RTC and getting other information from the module. The interface can operate in TEXT, HEX, or PDU modes (default: PDU).

Specifically, it provides a simple interface for sending messages (`send_sms()`), automatically handling multipart messages when needed. It also offers a high-level method (`read_next_message()`) to retrieve the next available message, abstracting message type and intelligently aggregating multipart content. It includes a high-level function (`http()`) for sending HTTP GET or POST requests, returning status and data in text or binary form. In addition, almost 30 specialized methods are available, to query the extensive proprietary information exposed by the SIM800 module.

## AT Protocol issues

This software manages SMS messaging and HTTP operations via the asyncronous serial communication of the SIM800 device, using its proprietary AT command protocol.

The AT command protocol is fundamentally inadequate for reliable and verifiable communication and presents intrinsic limitations when employed for robust operations. Originally designed for simple control of modems, the AT protocol is inherently textual and lacks the formal structure of communication protocols that utilize packetized data exchange.

One critical drawback lies in the nature of message formatting. AT commands are plain-text strings without explicit framing mechanisms. Unlike packet-based protocols, AT messages do not encapsulate data within headers that define payload length, type, or integrity information such as checksums or CRCs. Consequently, parsing and verifying the completeness and correctness of messages becomes error-prone.

Moreover, AT-based communication lacks a standardized state machine or signaling mechanisms to indicate distinct phases of a connection lifecycle. Commands that initiate, maintain, or terminate connections must be issued and interpreted in a predefined order, but the protocol itself does not return the transition between these states. This absence of inherent session management results in brittle implementations, where the client must continually probe the status of operations.

This deficiency becomes even more critical with vendor-specific instructions, which introduce proprietary connection setup sequences requiring polling or conditional branching based on context-sensitive responses, and may also include asynchronous "Unsolicited Result Codes" within the textual communication that needs special processing while managing the workflow. Without structured feedback or flags denoting session phases, the client application must rely on loosely coupled, often ambiguous responses to maintain protocol correctness.

Through an accurately tested heuristic approach, this software attempts to handle all supported operations via the AT protocol in the most robust manner possible, aiming to automatically recover from errors when feasible.

## Setup

This module only installs on Linux (not on Windows).

## Hw Requirements

- Linux system with a UART serial port, or Raspberry Pi with [Raspberry Pi OS](https://en.wikipedia.org/wiki/Raspberry_Pi_OS) (this library has been tested with Buster and Bullseye).
- External power supply for the SIM800L (using the Raspberry Pi 5V power supply, a standard diode (1N4007) with voltage drop of about 0.6 volts and a 1 F capacitor might work).

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

SIM800L does not support AT+HTTPSSL on [firmware](firmware/README.md) release <R14.00 (e.g., 1308B08SIM800L16 -> SIM800L R13.08 Build 08). Use a SIM800C if you need TLS.

For debugging needs, logs can be set to the maximum level (verbose mode, tracing each request/response) with the following command:

```python
import logging
logging.getLogger().setLevel(5)`
```

---

#### `sim800l = SIM800L(port="/dev/serial0", baudrate=115000, timeout=3.0, write_timeout=300, inter_byte_timeout=10, mode="PDU")`

Class instantiation (using [pySerial](https://github.com/pyserial/pyserial))

**Parameters:**
- `port` (str): Serial port (e.g., `/dev/serial0`).
- `baudrate` (int): Baud rate (default: 115000).
- `timeout` (float): Read timeout in seconds.
- `write_timeout` (int): Write timeout in seconds.
- `inter_byte_timeout` (int): Timeout between bytes during read.
- `mode` (str): SMS mode (`TEXT`, `HEX`, or `PDU`).

---

#### `check_sim()`
Checks if a SIM card is inserted.

**Returns:**  
- `True`: SIM inserted.
- `False`: SIM not inserted.
- `None`: Module error.

#### `get_date()`
Retrieves the module's internal clock date.

**Returns:**  
- `datetime.datetime`: Current date/time.
- `None`: Module error.

---

#### `is_registered()`
Checks if the SIM is registered on the home network.

**Returns:**  
- `True`: Registered.
- `False`: Not registered.
- `None`: Module error.

---

#### `get_operator()`
Gets the current network operator.

**Returns:**  
- `str`: Operator name.
- `False`: SIM error.
- `None`: Module error.

---

#### `get_battery_voltage()`

Returns battery voltage in volts.

Example: 4.158

**Returns:**  
- `float`: Voltage.
- `None`: Module error.

---

#### `send_sms(destno, msgtext, ...)`
Sends an SMS.

**Parameters:**
- `destno` (str): Destination phone number.
- `msgtext` (str): Message content.
- `validity` (int): SMS validity period (PDU mode).
- `smsc` (str): SMSC number (PDU mode).
- `requestStatusReport` (bool): Request delivery report.
- `rejectDuplicates` (bool): Reject duplicate messages.
- `sendFlash` (bool): Send as flash SMS.

**Returns:**  
- `True`: SMS sent successfully.
- `False`: Failed to send.

---

#### `connect_gprs(apn)`
Activates GPRS PDP context.

**Parameters:**
- `apn` (str): APN name for the carrier.

**Returns:**  
- `str`: Assigned IP address.
- `False`: Connection error.

---

#### `http(url, data=None, apn=None, ...)`

Run the HTTP GET method or the HTTP POST method and return retrieved data.

Automatically perform the full PDP context setup and close it at the end
(use keep_session=True to keep the IP session active). Reuse the IP
session if an IP address is found active.

Automatically open and close the HTTP session, resetting errors.

**Parameters:**
- `url` (str): Target URL.
- `data` (bytes): Payload for POST requests.
- `apn` (str): APN for GPRS connection.
- `method` (str): `GET` or `POST` (or `PUT`, same as `POST`).
- `use_ssl` (bool): Use HTTPS.
- `content_type` (str): HTTP Content-Type header.
- `http_timeout` (int): Timeout in seconds.
- `keep_session` (bool): Keep PDP context active.

**Returns:**  
- `status, str/bytes`: tuple including two values: HTTP status code (numeric, e.g., 200) and Response data (which can be text or binary).
- `False, None`: Request failed.

While the *Content type* header field can be set, the *Content encoding* is always null.

Sending data with [zlib](https://docs.python.org/3/library/zlib.html) is allowed:

```python
import zlib
body = zlib.compress('hello world'.encode())
status, ret_data = sim800l.http("...url...", method="POST", content_type="zipped", data=body, apn="...")
```

[Note on SSL](https://github.com/ostaquet/Arduino-SIM800L-driver/issues/33#issuecomment-761763635): SIM800L supports SSL2, SSL3 and TLS 1.0, but not TLS 1.2 (this is for any SIM800L known [firmwares](firmware/README.md) including Revision 1418B06SIM800L24); old cryptographic protocols are deprecated for all modern backend servers and the connection will be generally denied by the server, typically leading to SIM800L error 605 or 606 when establishing an HTTPS connection. Nevertheless, SIM800C supports TLS 1.2 with recent [firmwares](firmware/README.md) and with this device you can use `use_ssl=True`; setting a Python web server to support the SSL option of a SIM800L client module is not straightforward (it is better to use an [application encryption](https://stackoverflow.com/a/55147077/10598800) instead of SSL).

Notice also that, depending on the web server, a specific SSL certificate could be needed for a successful HTTPS connection; the SIM800L module has a limited support of SSL certificates and [installing an additional one](https://stackoverflow.com/questions/36996479/how-sim800-get-ssl-certificate
) is not straightforfard.

An additional problem is related to possible DNS errors when accessing endpoints. Using IP addresses is preferred.

---

#### `read_sms(index_id)`
Reads an SMS by index.

**Parameters:**
- `index_id` (int): SMS storage index (1-based).

**Returns:**  
- `tuple`: (origin, date, time, text).
- `None`: No message.
- `False`: Read error.

---

#### `delete_sms(index_id)`
Deletes an SMS by index.

**Parameters:**
- `index_id` (int): SMS storage index.

---

#### `hard_reset(reset_gpio)`
**Hardware reset via GPIO pin (RPi only).**  
*Parameters:*
- `reset_gpio`: BCM GPIO pin number

*Returns:*  
- `True`: Reset successful
- `None`: GPIO library unavailable

---

#### `set_date()`
Syncs the system clock with the module's time.

**Returns:**  
- `datetime.datetime`: Updated time.
- `None`: Module error.

---

#### `command(cmdstr, lines=-1, waitfor=500, msgtext=None, msgpdu=None, flush_input=True, timeout=2)`
**Sends raw AT commands to the module.**  

Executes an AT command. A newline must be added at the end of the AT command (e.g., `sim800l.command("AT+CCLK?\n", lines=-1)`).
Input is flushed before sending the command (`flush_input=False` disables flushing).

*Parameters:*
- `cmdstr`: AT command string (e.g., `"AT+CSQ"`)
- `lines`: Number of response lines to read (-1=read until timeout)
- `msgtext`: SMS text content (for SMS commands)
- `msgpdu`: PDU-formatted SMS (binary)
- `flush_input`: Clear input buffer before sending command
- `timeout`: Response timeout in seconds

*Returns:*  
- `str`: Raw response ("OK", "ERROR", or data lines)
- `"ERROR"` on serial write failure

If `lines=0`, terminates just after writing text to the device (no bytes read; no return code, e.g. `None` returned). Note: `check_incoming()` can be subsequently used to read data from the device (see subsequent example).

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

**Sends command and retrieves data before "OK".**  
*Parameters:*
- `cmd`: AT command (without trailing newline)
- `attempts`: Retry attempts before returning None or False

*Returns:*  
- `str`: Response data
- `None`: Module error
- `False`: Missing "OK"

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

#### `disconnect_gprs()`
**Deactivates GPRS PDP context.**  
*Returns:*  
- `True`: Success
- `False`: Error

---

#### `get_ccid()`
**Retrieves SIM ICCID.**  
*Returns:*  
- `str`: ICCID
- `None`: Module error

Example: "1122334455667788990f"

---

#### `get_flash_id()`
**Retrieves flash memory ID.**  
*Returns:*  
- `str`: Flash ID
- `None`: Error

Example: "Device Name:SERIAL§FLASH§MTKSIP§6261§SF§24§01"

---

#### `get_netlight()`
**Check the SIM800 Net Light Indicator.**
*Returns:*  
- 1: active,
- 0: inactive,
- `False`: error.

---

#### `get_hw_revision(method=0)`
**Gets hardware/firmware version.**  
*Parameters:*
- `method`:
  - 0 = Raw string
  - 1 = Parsed components
  - 2 = Alternate revision format

*Returns:*  
- `str`: Version info
- `None`: Error

Example: "Revision:1418B05SIM800L24"

---

#### `get_imsi()`
**Gets SIM IMSI number.**  
*Returns:*  
- `str`: IMSI
- `None`: Error

Example: "112233445566778"

---

#### `get_ip(poll_timeout=4)`
Get the IP address of the PDP context

*Parameter:*
- `poll_timeout`: optional poll setting in seconds to wait for the IP address to return as +SAPBR: 1,1,"...".

*Returns:*  
- valid IP address string if the bearer is connected
- `None`: Bearer not connected, no IP address
- `False`: Error (e.g., module error)

---

#### `get_msgid()`
Return the unsolicited notification of incoming SMS
 *return*: number

---

#### `get_msisdn()`
Get the MSISDN subscriber number
 *return*: string. `None` in case of module error.

---

#### `get_operator_list()`
**Lists all available network operators.**  
*Returns:*  
- `dict`: {numeric_code: "Operator Name"}
- `None`: Error

---

#### `get_serial_number()`
**Retrieves module serial number.**  
*Returns:*  
- `str`: Serial
- `None`: Error

Example: "866782042319455"

---

#### `get_service_provider()`
Get the Get Service Provider Name stored inside the SIM
 *return*: string. `None` in case of module error. `False` in case of SIM error.

---

#### `get_signal_strength()`
**Gets signal strength (0-100%).**  
*Returns:*  
- `int`: Signal percentage
- `None`: Error

Example: 40.625

---

#### `get_temperature()`
**Gets module temperature.**  
*Returns:*  
- `str`: Temperature in Celsius
- `None`: Error

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

#### `read_and_delete_all(index_id=0, delete=True)`
**Reads and deletes all SMS messages.**  

Read the message at position 1, otherwise delete all SMS messages, regardless the type (read, unread, sent, unsent, received).
If the message is succesfully retrieved, no deletion is done. (Deletion only occurs in case of retrieval error.)
Notice that, while generally message 1 is the first to be read, it might happen that no message at position 1 is available,
while other positions might still include messages; for those cases (missing message at position 1, but other messages
available at other positions), the whole set of messages is deleted.

*Parameters:*
- `index_id`: Starting index
- `delete`: Whether to delete after reading

*Returns:*  
- `str`: Message text
- `None`: No messages
- `False`: Error

---

#### `read_next_message(all_msg=False, index=0, delete=True, tuple=False, concatenate=False, delta_min=15)`
Check messages, read one message and then delete it. This function can be repeatedly called to read all stored/received messages one by one and delete them.
- `all_msg`: `True` if no filter is used (read and unread messages).  Otherwise only the unread messages are returned.
 *return*: retrieved message text (string), otherwise: `None` = no messages to read; `False` = read error (module error)

Check messages, read one message and then delete it. This function can be repeatedly called to read all stored/received messages one by one and delete them.
Aggregate multipart PDU messages. Only delete messages if there are no errors.

- `all_msg`: `True` if no filter is used (return both read and non read messages). Otherwise, only the non read messages are returned.
- `index`: read index message in processed array; default is the first one.
- `delete`: delete the message after reading it.
- `tuple`: returns a tuple instead of the plain text. Tuple: `[MSISDN origin number, SMS date string, SMS time string, SMS text]`
- `concatenate`: concatenate text messages (text mode) when read message is > 150 chars. Not reliable (suggest using PDU mode)
- `delta_min`: max time in minutes to keep uncompleted multipart undecoded (allowing to wait for its completion)

 *return*: retrieved message text (string), otherwise: `None` = no messages to read; `False` = read error (module error)

---

#### `serial_port()`
Return the serial port (for direct debugging)
 *return*:

---

#### `setup(disable_netlight=False)`
Run setup strings for the initial configuration of the SIM800 module

- `disable_netlight`: `True` if the Net Light LED has to be disabled (default is to enable it).

 *return*: `True` if setup is successfully completed; `None` in case of module error.

---

#### `check_incoming()`
Internal function, used to check incoming data from the SIM800L module, decoding messages.
It also fires the functions configured with `callback_incoming()`, `callback_msg()`, `callback_clip()` and `callback_no_carrier()`.
 *return*: tuple

Return values:
- `('GENERIC', None)`: no data received
- `('GENERIC', data)`: received data is returned (`data` is a string)
- `("HTTPACTION_POST", False, size)`: invalid HTTP POST method, with return code different from 200
- `("HTTPACTION_POST", True, size)`: valid HTTP POST method; `size` is the number of returned characters
- `("HTTPACTION_PUT", False, size)`: invalid HTTP PUT method (same as POST, depending on the parameter to invoke `http()`), with return code different from 200
- `("HTTPACTION_PUT", True, size)`: valid HTTP PUT method (same as POST, depending on the parameter to invoke `http()`); `size` is the number of returned characters
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
**Sets HEX character encoding.**  

Set the module to the HEX character set (only hexadecimal values from 00 to FF)

*Returns:*  
- `"OK"` if successful, otherwise `None` in case of module error.

---

#### `set_charset_ira()`
Set the module to the International reference alphabet (ITU-T T.50) character set
 *return*: "OK" if successful, otherwise `None` in case of module error.

---

#### `set_charset_gsm()`
**Sets GSM 03.38 encoding (default).**  
*Returns:*  
- `"OK"` if successful

---

#### `convert_to_string(buf)`

Decode GSM 03.38 encoded bytes, returning a string.

**Parameters:**
- `buf` (bytes): GSM 03.38 encoded data (bytes).

**Returns:**  
`str` - Decoded UTF-8 string.

---

#### `convert_gsm(string)`

Encode `string` to bytes using the 3GPP TS 23.038 / ETSI GSM 03.38 codec.

**Parameters:**
- `string` (str): Input string.

**Returns:**  
`bytes` - Encoded GSM 03.38 data.

---

## Notes

- **PDU Mode**: Recommended for handling long SMS and multipart messages.
- **GPRS**: Ensure correct APN settings for your carrier.
- **HTTP**: SIM800L supports TLS 1.0 only (modern servers may reject connections); SIM800C supports TLS 1.2.

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

#### HTTP POST sample
```python
print(sim800l.http("httpbin.org/post", data='{"name","abc"}'.encode(), method="POST", apn="..."))  # HTTPS
print(sim800l.http("httpbin.org/post", data='{"name","abc"}'.encode(), method="POST", use_ssl=False, apn="..."))  # HTTP
```

#### Read the n-th SMS
```python
Read the SMS indexed by the index_id value [ref. also check_incoming()]
index_id=...  # e.g., 1
sim800l.read_sms(index_id)
```

#### Callback actions

Unsolicited Result Codes can be optionally configured to fire respective functions.

Unsolicited Result Code |Configuration method                            |Corresponding fired function and argument
------------------------|------------------------------------------------|----------------------------
RING                    |sim800l.callback_incoming(incoming_function)    |incoming_function()
NO CARRIER              |sim800l.callback_no_carrier(incoming_function)  |incoming_function()
+CMTI                   |sim800l.callback_msg(message_function)          |message_function(message_index)
+CLIP                   |sim800l.callback_clip(calling_function)         |calling_function(calling_msisdn_number)

Setup example:

```python
def alert_new_message():
    print("Incoming SMS message")

sim800l.callback_msg(alert_new_message)
```

#### `callback_incoming(action)`
Sets a callback for incoming calls.

**Parameters:**
- `action` (function): Function to trigger on incoming call.

---

#### `callback_no_carrier(action)`
Sets a callback for call disconnection.

**Parameters:**
- `action` (function): Function to trigger on disconnect.

---

#### `callback_msg(action)`

Configure a callback function, fired when `check_incoming()` receives a message (`+CMTI` returned, indicating new message received).

**Sets callback for incoming SMS.**  
*Parameters:*
- `action`: Function to call on `+CMTI` alert

#### `callback_clip(action)`

Configure a callback function, fired when `check_incoming()` detects an incoming voice call (`+CLIP` returned, indicating incoming voice call detected).

**Sets callback for incoming voice call.**  
*Parameters:*
- `action`: Function to call on `+CLIP` alert

-----------

Examples:

```python
from sim800l import SIM800L

MSISDN = "+..."
APN= "..."

# To improve the logging level:
#import logging
#logging.getLogger().setLevel(5)
 
sim800l=SIM800L()

ret = sim800l.setup()
if not ret:
    quit()

print("Result of get_netlight", sim800l.get_netlight())
print("Result of check_sim", sim800l.check_sim())
print("Result of get_date", sim800l.get_date())
print("Result of is_registered", sim800l.is_registered())
print("Result of get_operator", sim800l.get_operator())
print("Result of get_operator_list", sim800l.get_operator_list())
print("Result of get_service_provider", sim800l.get_service_provider())
print("Result of get_battery_voltage", sim800l.get_battery_voltage())
print("Result of get_msisdn", sim800l.get_msisdn())
print("Result of get_signal_strength", sim800l.get_signal_strength())
print("Result of get_unit_name", sim800l.get_unit_name())
print("Result of get_hw_revision", sim800l.get_hw_revision())
print("Result of get_serial_number", sim800l.get_serial_number())
print("Result of get_ccid", sim800l.get_ccid())
print("Result of get_imsi", sim800l.get_imsi())
print("Result of get_temperature", sim800l.get_temperature())
print("Result of get_flash_id", sim800l.get_flash_id())
print("Result of get_ip", sim800l.get_ip())

rec = sim800l.send_sms(MSISDN, "The quick brown fox jumps over the lazy dog.")
print("Result of sent short SMS:", repr(rec))

rec = sim800l.send_sms(MSISDN, "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.")
print("Result of sent long SMS:", repr(rec))

rec = False
while rec is not None:
    rec = sim800l.read_next_message(all_msg=True)
    print("Received SMS message:", repr(rec))

rec = sim800l.http("httpbin.org/ip", method="GET", apn=APN, binary=True)
print("HTTP", repr(rec))

rec = sim800l.http("httpbin.org/post", data='{"name","abc"}'.encode(), method="POST", apn=APN)
print("HTTP", repr(rec))

rec = sim800l.http("https://httpbin.org/post", data='{"name","abc"}'.encode(), method="POST", apn=APN, use_ssl=True)
print("HTTP", repr(rec))

rec = sim800l.http("https://www.google.com/", method="GET", apn=APN, use_ssl=True)
print("HTTP", repr(rec))
```

-----------

## References
- [AT Datasheet](https://microchip.ua/simcom/2G/SIM800%20Series_AT%20Command%20Manual_V1.12.pdf)
- [Application notes](https://www.microchip.ua/simcom/?link=/2G/Application%20Notes)
- [Specifications](https://simcom.ee/documents/?dir=SIM800L)

Arduino:
- https://github.com/vshymanskyy/TinyGSM
- https://lastminuteengineers.com/sim800l-gsm-module-arduino-tutorial/

## History
This library is a fork of the original library https://github.com/jakhax/raspberry-pi-sim800l-gsm-module with a wide set of additions.

> SIM900/SIM800 are 2G only modems, make sure your provider supports 2G as it is already being phased out in a lot of areas around the world, else a 3G/4G modem like the SIM7100 / SIM5300 is warranted.  
