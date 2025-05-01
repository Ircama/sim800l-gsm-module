# Upgrading the SIM800L firmware with a Raspberry Pi

## Foreword

Details of the upgrade procedure are included in the "SIM800 Series_Software Upgrade_Application Note_V1.05" document from https://www.simcom.com/product/SIM800H.html.

Old firmwares:

- [1308B04SIM800L16](https://github.com/koson/simcom/blob/master/documents/SIM800L/1308B04SIM800L16.rar).
- [1308B09SIM800L16](https://simcom.ee/documents/SIM800L/1308B09SIM800L16.rar).
- [1418B04SIM800C24](https://github.com/ZeroPhone/SIM800-firmwares/tree/master/1418B04SIM800C24).
- [1418B05SIM800C24](https://github.com/ZeroPhone/SIM800-firmwares/tree/master/1418B05SIM800C24).

*1418B06SIM800L24* might possibly be the latest firmware for SIM800L.

Old *13...SIM800L16* firmwares (16 Mbit flash) cannot be flashed on SIM800L 24 Mbit flash with this procedure.

Disclaimer: Firmware version *1418B06SIM800L24* was sourced from an [online repository](https://s27.picofile.com/file/8458398618/1418B06SIM800L24.rar.html), and its authenticity and origin cannot be verified. Users are advised to exercise caution and are encouraged to notify any official updates, improved versions, or reliable alternatives to ensure optimal performance and security.

SIM800L can theoretically install the lastest firmware for the SIM800C, which does include TLS 1.2 support, but other incompatibilities might arise, like the NETLIGHT LED pin mapped to pin 41 in SIM800C, while SIM800L needs pin 64. If you install the SIM800C firmware to SIM800L (discouraged), pin 64 (the standard LED pin on SIM800L) will not be used and pin 41 will be HIGH or LOW according to each blink, possibly compromising the hardware depending on how pin 41 is connected on SIM800L (the blink can be disabled via `AT+CNETLIGHT=0` and `AT&W`).

Where firmwares were found (not official fonts in any case):

- [1418B07SIM800C24_BT](https://simcom.ee/documents/SIM800C/1418B07SIM800C24_BT.RAR) or [here](https://github.com/Edragon/SIMCOM_upgrade/tree/main/sim800) or [here](https://github.com/Edragon/SIMCOM_upgrade/blob/main/sim800/1418B07SIM800C24_BT.rar)
- [1418B08SIM800C24](https://techship.com/downloads/simcom-sim800c-1418b08sim800c24-firmware-update-files-and-release-note/)
- [1418B09SIM800C24_TLS12](https://github.com/nimaltd/nimaltd.github.io/blob/master/1418B09SIM800C24_TLS12.rar) or [here](https://s25.picofile.com/file/8452279234/1418B09SIM800C24_TLS12.rar.html)
- 1418B10SIM800C24_TLS12

## mtkdownload tool

This is an improved procedure of the original [mtkdownload.c](https://github.com/ZeroPhone/mtkdownload). 

The *mtkdownload* tool is designed to flash firmware onto SIM800L/SIM800H/SIM800C modules via a serial connection, providing a low-level interface for updates. This version (tested on a Raspberry Pi) also includes additional controls, improved messages, embedded device reboot to automatically start the upload, embedded port reset, a dry-run option, and version number reporting before and after the upgrade.

Command Syntax:

```
Usage: mtkdownload <com> ROM_VIVA <format> [<port>]

<com>: e.g., /dev/serial0, /dev/ttyS0, /dev/ttyS1, /dev/ttyS2...

ROM_VIVA: name of the ROM file

<format> can be Y=format FAT, S=like Y + disable netlight,
         N=skip FAT formatting, T=dry run.

<port> optional Raspberry Pi BCM port number for performing reset. If 0:
no upgrade, only read fw version; if negative: same as 0, with device reset.

The device is also rebooted via software command; this is useful if the device
is operative before the upgrade starts and when <port> (hard reset) is not used.

Examples:

mtkdownload /dev/serial0 ROM_VIVA Y
Ask manual reset of the device, format the storage, perform the upgrade.

mtkdownload /dev/serial0 ROM_VIVA Y 24
Auto reset the device through GPIO 24, format the storage, perform the
upgrade. 24 means GPIO BCM 24, equivalent to pin 18.

mtkdownload /dev/serial0 ROM_VIVA T 24
Auto reset the device through GPIO 24, perform a dry run of the upgrade
operation.

mtkdownload /dev/serial0 ROM_VIVA Y 0
No upgrade, just read the firmware version.

mtkdownload /dev/serial0 ROM_VIVA Y -24
No upgrade, just read the firmware version and reset the device via GPIO
BCM 24.
```

If the port is 0, the software reads the current firmware version and exit without performing the upgrade.

If the port is negative (e.g., -24), the software reads the current firmware version, resets the device and exits without performing the upgrade.

If `<format>` is 'S', format FAT and also disable netlight at the end of the upgrade.

If `<format>` is 'T', a dry-run procedure is executed testing port communication and GPIO reset, with output similar to the following (for `./mtkdownload /dev/serial0 .../ROM_VIVA T ...`):

```
Tty serial port configuration completed.
Ready to send and receive data.
Clear all terminal serial port status bits succeeded (returned 0).
Port is a tty (valid device).
Filename : .../ROM_VIVA
Filesize : ... bytes
ROM length ... bytes
Dry-run mode.
Contacting the device.

Current firmware version:
AT+CGMR;+CNETLIGHT?
Revision:...

+CNETLIGHT: 1

OK

Hard reset of port ... complete.

SEND 1 Byte b5. RECV 1 Byte 5b.

Device entered in upgrade mode.
SEND 'Restart'                  1 Byte  0x07
RECV 'restart' resp:            1 Byte  0x4d
'M' ('Command error') received. Flushing 'M' characters, please wait for about 30 seconds...
Operation completed. Sleep for 5 seconds...

Current firmware version:
AT+CGMR;+CNETLIGHT?
+CPIN: READY

Revision:...

+CNETLIGHT: 1

OK
```

Example of a valid upgrade:

```
Tty serial port configuration completed.
Ready to send and receive data.
Clear all terminal serial port status bits succeeded (returned 0).
Port is a tty (valid device).
Filename : .../ROM_VIVA
Filesize : ... bytes
ROM length ... bytes
Dry-run mode.
Contacting the device.

Current firmware version:
AT+CGMR;+CNETLIGHT?

Revision:...

+CNETLIGHT: 1

OK

Hard reset of port ... complete.

SEND 1 Byte b5. RECV 1 Byte 5b.

Device entered in upgrade mode.
Please wait for flash erase to finish.
SEND 1 Byte 81
SEND 128 Bytes, please wait erasure ('R' sequence) to complete with '02'...
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R ]
[ R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R R 02 ]

Erase done. Reading the subsequent two bytes (maximum packet length 0x00, 0x08).
RECV  1 Byte    0x00
RECV  1 Byte    0x08

Uploading ROM_VIVA File to the module.
ROM 100  ... bytes sent.   ROM upload completed!
SEND 'Update end':              1 Byte  0x05
RECV 'Update end' resp:         1 Byte  0x06
SEND 'Restart'                  1 Byte  0x07
RECV 'restart' resp:            1 Byte  0x08
Operation completed. Sleep for 5 seconds...

Current firmware version:
AT+CGMR;+CNETLIGHT?
+CPIN: READY

Revision:...

+CNETLIGHT: 1

OK
```

Notes:

- `Revision:...` shows the firmware version.
- `+CPIN: READY` might be shown and it means that the SIM card is correctly recognised.
- `+CNETLIGHT: 1` means that the Network Status Indication LED is in use.


## Upgrade procedure

Compile the code (`make`).

Ensure the SIM800L module is properly connected to the Raspberry Pi via serial interface.

Ensure the serial interface to the SIM800L module is not used by any other application.

Enter the firmware directory and point to the ROM_VIVA file.

Power on the module.

Run the upgrade procedure.

```bash
cd firmware
make
mtkdownload /dev/serial0 1418B06SIM800L24/ROM_VIVA Y 24
```

If the reset port is used, the upgrade is automatic, otherwise short the RST (Reset) pin to GND to reset the module, then release it. The tool sends sync bytes (0xB5) and waits for the module’s response (0x5B). From the documentation:

> When the module Bootloader program starts, if it receives the 0xB5 byte synchronization word within 100 ms, it will reply with a 0x5B byte word then the module go into the upgrade mode. Within 100 ms, if the module does not receive 0xB5 synchronization word, the module will enter normal mode.

If Y is specified (suggested), the tool also erases the FAT storage before flashing.

> In the version upgrade, such as upgrading from B01 to B02 version, you should erase the file system.

The firmware is split into 512-byte blocks. Each block is sent with a checksum for validation. Progress is displayed as a percentage. After transferring all data, the tool reboots automatically.

Serial port configuration: Baud Rate: 115200. Data Bits: 8, Stop Bits: 1, Parity: None

## Chip Differences

### SIM800L

- Generally S2-1065J-Z1435

- GSM 850,900,1800 and 1900MHz
- No Bluetooth support
- 24Mbit FLASH (3MB)
- 32Mbit RAM
- Power supply 3.4V ~ 4.4V
- 88 pins chip
- NETLIGHT on pin 64 (Network Status Indication LED)

SIM800L includes a MediaTek MT6261MA SoC (GSM/GPRS, Bluetooth and FM with 3MB/24Mb NOR Flash) and a RF7176 IC (quad-band GSM/GPRS power amplifier module). The MediaTek MT6261MA SoC is a baseband processor widely used in older low-cost mobile phones and implements only 2G (GSM/GPRS), with no support for 3G or newer cellular technologies.

The size of ROM_VIVA firmware (combining EXT_BOOTLOADER, ROM code and the VIVA voice/audio interface that enables phone call audio paths, ringtone playback, and other audio features) shall be smaller than 3 MB.

### SIM800H

Same as SIM800L with 32Mbit FLASH (4MB)

### SIM800C

- S2-10686-Z1L1D
- S2-108K7-Z1L25

- 24Mbit FLASH
- 32Mbit RAM
- NETLIGHT on pin 41 (Network Status Indication LED)
- 42 pin chip
- Bluetooth enabled via special firmware
- Power supply 3.4V ~4.4V

- Option SIM800C32 with 32Mbit FLASH

### **Simcom 2G Module Product Line Selection**

From some docs:

| Product Name | P/N        | Remarks                                                                 |
|--------------|------------|------------------------------------------------------------------------|
| SIM800L      | S2-1065J   | 24M version           S2-10766                                         |
| SIM800L      | S2-105HE   | MediaTek MT6261MA                                                     |
| SIM800L      | S2-1065J   | Mediatek MT6261                                                       |
| SIM800L      | S2-1065L   | S2-107CC                                                              |
| SIM800L      | S2-1065S   | S2-1065S-Z1442                                                        |
| SIM800C      | S2-10686   | 24M version BT, main product for overseas markets, 1418B07SIM800C24_BT |
| SIM800C      | S2-1068F   | 24M version BT, main product for overseas markets, tape and reel packaging, 1418B08SIM800C24_BT |
| SIM800C-L    | S2-1068S   | 24M basic version, domestic PA, promoted for domestic, Eastern Europe, India, and other low-end overseas markets, 1418B06SIM800C24 |
| SIM800C-S    | S2-108KB   | 16M version, domestic PA, promoted for domestic and low-end overseas markets, no Bluetooth support |
| SIM800C32    | S2-10688   | 32M version, main product for overseas markets                        |
| SIM800C32    | S2-1068L   | 32M version, main product for overseas markets, tape and reel packaging |
| SIM800C32-L  | S2-1068T   | 32M version, domestic PA                                              |
| SIM800C-DS   | S2-1068B   | Supports dual SIM dual standby                                        |
| SIM800       | S2-105MB   | MT6260D platform                                                      |
| SIM800       | S2-105MV   | MT6260D platform, tape and reel packaging                             |
| SIM800H      | S2-1065N   | MT6260D platform  (S2-1065N-Z142K, S2-1065N-Z142D, S2-1065N-Z1436)     |
| SIM800H      | S2-1065Q   | MT6260D platform, tape and reel packaging  (S2-1065Q-Z142D)            |
| SIM800A      | S2-106B6   | 24M version                                                           |
| SIM800A-L    | S2-10761   | 24M version, domestic PA                                              |
| SIM800A32    | S2-106BB   | 32M version                                                           |
| SIM800A32-L  | S2-10763   | 32M version, domestic PA                                              |
| SIM800F      | S2-106BA   | 32M version, main product                                             |
| SIM800F      | S2-106BT   | 32M version, tape and reel packaging                                  |
| SIM800F64    | S2-106BH   | 64M version                                                           |
| SIM808       | S2-1060C   | MT6261D + MT3337                                                      |
| SIM868       | S2-106R4   | Promoted in Western Europe and South America                          |
| SIM868-L     | S2-108J1   | Domestic PA, promoted for domestic, India, Eastern Europe, etc. (low-end markets) |
| SIM868E      | S2-106RB   | Supports Bluetooth                                                    |
| SIM868E-L    | S2-108J8   | Supports Bluetooth, domestic PA                                       |
| R800C        | S2-107JA   | UNISOC 8955L platform                                                 |
| R805C        | S2-107JC   | UNISOC 8955L platform                                                 |

## Reboot loops and communication errors

Reboot loops are typically caused by an inadequate power supply, leading to voltage drops when the module demands high current — up to 2A pulses — during RF transmission for network connectivity. If a standard diode is used for voltage dropping from 5V, it is recommended to place a 1 F low-ESR capacitor (or supercapacitor) as close as possible to the IC’s VCC pin to stabilize the supply during high current transients. With reboot loops, check also how the LED is connected.

https://electronics.stackexchange.com/questions/359308/upgrading-firmware-of-sim800c

https://electronics.stackexchange.com/questions/274065/gsm-module-gets-into-reboot-loop

Incorrect voltage levels may cause serial communication errors (115200,N,8,1 should not get errors with normal power supply).

Messages like the following might be due to improper power supply at boot:

```
F1: 5004 0000
00: 102C 0001
01: 1005 0000
U0: 0000 0001 [0000]
T0: 0000 00A3
Boot failed, reset ...
```

## TLS Support

The following code tests the TLS support of the firmware.

```python
############################
# Test 1 - write test_tls.html (open it with a browser)
APN="..."

from sim800l import SIM800L
sim800l = SIM800L()
sim800l.setup()

a = sim800l.http(
    "https://clienttest.ssllabs.com:8443/ssltest/viewMyClient.html",
    method="GET",
    apn=APN,
    use_ssl=True
)
b = a[1].replace(
    '/includes/', 'https://clienttest.ssllabs.com:8443/includes/'
).replace(
    'src="/images/', 'src="https://clienttest.ssllabs.com:8443/images/'
).replace(
    'src=/images/', 'src=https://clienttest.ssllabs.com:8443/images/'
).replace(
    '<script type="text/javascript" src="https://clienttest.ssllabs.com:8443/includes/viewClient.js"></script>', ""
).replace(
    '<script type="text/javascript" src="https://clienttest.ssllabs.com:8443/includes/viewClient-appleTest.js"></script>', ""
).replace(
    '<script type="text/javascript" src="https://clienttest.ssllabs.com:8443/includes/viewClient-clientTest.js"></script>', ""
)

with open("test_tls.html", "w") as text_file:
    text_file.write(b)

############################
# test 2 - fails https://browserleaks.com/tls because the web server requires TLS 1.3 and the firmware does not support it.
ret = sim800l.http("https://browserleaks.com/tls", method="GET", apn=APN, use_ssl=True)  # this returns (606, '') because requires TLS 1.3
# Status code 606 is SSL fatal alert message with immediate connection termination

############################
# Test 3 - report TLS characteristics
import json
from pprint import pprint
a = sim800l.http("https://www.howsmyssl.com/a/check", method="GET", apn="mobile.vodafone.it", use_ssl=True)
pprint(json.loads(a[1]))
```

### Output produced by firmware 1418B06SIM800L24

TLS 1.1, 1.2 and 1.3 are not supported.

#### Protocols

| Protocol   | Supported |
|------------|-----------|
| TLS 1.3    | No        |
| TLS 1.2    | No        |
| TLS 1.1    | No        |
| TLS 1.0    | Yes*      |
| SSL 3      | Yes*      |
| SSL 2      | No        |

#### Cipher Suites (in order of preference)

| Cipher Suite | Strength |
|--------------|----------|
| **`TLS_RSA_WITH_RC4_128_MD5 (0x4)` INSECURE** | **128** |
| **`TLS_RSA_WITH_RC4_128_SHA (0x5)` INSECURE** | **128** |
| `TLS_RSA_WITH_AES_128_CBC_SHA (0x2f)` WEAK | 128 |
| `TLS_DHE_RSA_WITH_3DES_EDE_CBC_SHA (0x16)` WEAK | 112 |
| `TLS_DHE_DSS_WITH_3DES_EDE_CBC_SHA (0x13)` WEAK | 112 |
| `TLS_RSA_WITH_3DES_EDE_CBC_SHA (0x0a)` WEAK | 112 |
| **`TLS_RSA_WITH_DES_CBC_SHA (0x09)` INSECURE** | **56** |
| **`TLS_RSA_EXPORT_WITH_RC4_40_MD5 (0x03)` INSECURE** | **40** |
| **`TLS_DHE_DSS_WITH_DES_CBC_SHA (0x12)` INSECURE** | **56** |

#### Protocol Details

| Feature                                     | Value       |
|--------------------------------------------|-------------|
| Server Name Indication (SNI)               | No          |
| **Secure Renegotiation**                   | **No – INSECURE** |
| TLS compression                            | No          |
| Session tickets                            | No          |
| OCSP stapling                              | No          |
| Signature algorithms                       | -           |
| Named Groups                               | -           |
| Next Protocol Negotiation                  | No          |
| Application Layer Protocol Negotiation     | No          |
| SSL 2 handshake compatibility              | No          |

#### TLS characteristics

```python
{'able_to_detect_n_minus_one_splitting': True,
 'beast_vuln': False,
 'ephemeral_keys_supported': True,
 'given_cipher_suites': ['TLS_RSA_WITH_RC4_128_MD5',
                         'TLS_RSA_WITH_RC4_128_SHA',
                         'TLS_RSA_WITH_AES_128_CBC_SHA',
                         'TLS_DHE_RSA_WITH_3DES_EDE_CBC_SHA',
                         'TLS_DHE_DSS_WITH_3DES_EDE_CBC_SHA',
                         'TLS_RSA_WITH_3DES_EDE_CBC_SHA',
                         'TLS_RSA_WITH_DES_CBC_SHA',
                         'TLS_RSA_EXPORT_WITH_RC4_40_MD5',
                         'TLS_DHE_DSS_WITH_DES_CBC_SHA'],
 'insecure_cipher_suites': {'TLS_DHE_DSS_WITH_3DES_EDE_CBC_SHA': ['uses 3DES '
                                                                  'which is '
                                                                  'vulnerable '
                                                                  'to the '
                                                                  'Sweet32 '
                                                                  'attack but '
                                                                  'was not '
                                                                  'configured '
                                                                  'as a '
                                                                  'fallback in '
                                                                  'the '
                                                                  'ciphersuite '
                                                                  'order'],
                            'TLS_DHE_DSS_WITH_DES_CBC_SHA': ['uses keys '
                                                             'smaller than 128 '
                                                             'bits in its '
                                                             'encryption'],
                            'TLS_DHE_RSA_WITH_3DES_EDE_CBC_SHA': ['uses 3DES '
                                                                  'which is '
                                                                  'vulnerable '
                                                                  'to the '
                                                                  'Sweet32 '
                                                                  'attack but '
                                                                  'was not '
                                                                  'configured '
                                                                  'as a '
                                                                  'fallback in '
                                                                  'the '
                                                                  'ciphersuite '
                                                                  'order'],
                            'TLS_RSA_EXPORT_WITH_RC4_40_MD5': ['uses keys '
                                                               'smaller than '
                                                               '128 bits in '
                                                               'its encryption',
                                                               'uses RC4 which '
                                                               'has insecure '
                                                               'biases in its '
                                                               'output'],
                            'TLS_RSA_WITH_3DES_EDE_CBC_SHA': ['uses 3DES which '
                                                              'is vulnerable '
                                                              'to the Sweet32 '
                                                              'attack but was '
                                                              'not configured '
                                                              'as a fallback '
                                                              'in the '
                                                              'ciphersuite '
                                                              'order'],
                            'TLS_RSA_WITH_DES_CBC_SHA': ['uses keys smaller '
                                                         'than 128 bits in its '
                                                         'encryption'],
                            'TLS_RSA_WITH_RC4_128_MD5': ['uses RC4 which has '
                                                         'insecure biases in '
                                                         'its output'],
                            'TLS_RSA_WITH_RC4_128_SHA': ['uses RC4 which has '
                                                         'insecure biases in '
                                                         'its output']},
 'rating': 'Bad',
 'session_ticket_supported': False,
 'tls_compression_supported': False,
 'tls_version': 'TLS 1.0',
 'unknown_cipher_suite_supported': False}
```

### Output produced by firmware 1418B09SIM800C24_TLS12

TLS 1.3 is not supported.

#### Protocols

| Protocol | Supported |
|:---------|:----------|
| TLS 1.3 | No |
| TLS 1.2 | Yes* |
| TLS 1.1 | Yes* |
| TLS 1.0 | Yes* |
| SSL 3   | Yes* |
| SSL 2   | No |

> (*) Without JavaScript, this test reliably detects only the highest supported protocol.

#### Cipher Suites (in order of preference)

| Cipher Suite | Strength |
|:-------------|:---------|
| **TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256** (`0xc02b`) — *Forward Secrecy* | 128 |
| **TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256** (`0xc02f`) — *Forward Secrecy* | 128 |
| **TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256** (`0xc023`) — **WEAK** | 128 |
| **TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256** (`0xc027`) — **WEAK** | 128 |
| **TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA** (`0xc009`) — **WEAK** | 128 |
| **TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA** (`0xc013`) — **WEAK** | 128 |
| **TLS_RSA_WITH_AES_128_GCM_SHA256** (`0x9c`) — **WEAK** | 128 |
| **TLS_RSA_WITH_AES_128_CBC_SHA256** (`0x3c`) — **WEAK** | 128 |
| **TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA** (`0xc014`) — **WEAK** | 256 |
| **TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA** (`0xc00a`) — **WEAK** | 256 |

> (1) When a browser supports SSL 2, its SSL 2-only suites are shown only on the very first connection to this site.  
> To see the suites, close all browser windows, then open this exact page directly. Don't refresh.

#### Protocol Details

| Feature | Supported |
|:--------|:----------|
| **Server Name Indication (SNI)** | No |
| **Secure Renegotiation** | **No — INSECURE** |
| **TLS compression** | No |
| **Session tickets** | No |
| **OCSP stapling** | No |
| Signature algorithms | - |
| Named Groups | - |
| Next Protocol Negotiation | No |
| Application Layer Protocol Negotiation | No |
| **SSL 2 handshake compatibility** | No |

#### TLS characteristics

```python
{'able_to_detect_n_minus_one_splitting': False,
 'beast_vuln': False,
 'ephemeral_keys_supported': True,
 'given_cipher_suites': ['TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256',
                         'TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256',
                         'TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256',
                         'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256',
                         'TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA',
                         'TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA',
                         'TLS_RSA_WITH_AES_128_GCM_SHA256',
                         'TLS_RSA_WITH_AES_128_CBC_SHA256',
                         'TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA',
                         'TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA'],
 'insecure_cipher_suites': {},
 'rating': 'Probably Okay',
 'session_ticket_supported': False,
 'tls_compression_supported': False,
 'tls_version': 'TLS 1.2',
 'unknown_cipher_suite_supported': False}
```
