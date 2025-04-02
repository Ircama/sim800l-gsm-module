# Upgrading the SIM800L firmware with a Raspberry Pi

## Foreword

Details of the upgrade procedure are included in the "SIM800 Series_Software Upgrade_Application Note_V1.05" document from https://www.simcom.com/product/SIM800H.html.

Old firmware: [1308B09SIM800L16](https://simcom.ee/documents/SIM800L/1308B09SIM800L16.rar).

*1418B06SIM800L24* might possibly be the latest firmware for SIM800L.

Disclaimer: Firmware version *1418B06SIM800L24* was sourced from an online repository, and its authenticity and origin cannot be verified. Users are advised to exercise caution and are encouraged to notify any official updates, improved versions, or reliable alternatives to ensure optimal performance and security.

## mtkdownload tool

The *mtkdownload* tool is designed to flash firmware onto SIM800L/SIM800H modules via a serial connection, providing a low-level interface for updates.

Command Syntax:

```
mtkdownload <com_port> <firmware_file> <format_flag>

<com_port>: Serial port device (e.g., /dev/serial0).

<firmware_file>: Path to the firmware binary (e.g., ROM_VIVA).

<format_flag>:

Y: Format the device’s FAT storage before flashing.

N: Flash without formatting.

Example: mtkdownload /dev/serial0 ROM_VIVA Y
```

## Upgrade procedure

Compile the code.

Ensure the SIM800L module is properly connected to the Raspberry Pi via serial interface.

Enter the firmware directory and point to the ROM_VIVA file.

Power on the module.

Run the upgrade procedure.

```bash
cd firmware
make
cd 1418B06SIM800L24
../mtkdownload /dev/serial0 ROM_VIVA Y
```

Short the RST (Reset) pin to GND to reset the module.

The tool sends sync bytes (0xB5) and waits for the module’s response (0x5B).

> When the module Bootloader program starts, if it receives the 0xB5 byte synchronization word within 100 ms, it will reply with a 0x5B byte word then the module go into the upgrade mode. Within 100 ms, if the module does not receive 0xB5 synchronization word, the module will enter normal mode.

The the sync loop waits for detection of the correct sequence. Remove the RST-GND short 10 seconds after the sync loop starts.

If Y is specified, the tool also erases the FAT storage before flashing. The tool confirms erase completion via CMD_DL_BEGIN_RSP.

> In the version upgrade, such as upgrading from B01 to B02 version, you should erase the file system.

The firmware is split into 512-byte blocks. Each block is sent with a checksum for validation. Progress is displayed as a percentage. After transferring all data, the tool sends CMD_DL_END to finalize the process. The module reboots automatically (CMD_RUN_GSMSW command).

Serial Port Configuration: Baud Rate: 115200. Data Bits: 8, Stop Bits: 1, Parity: None

Warning: interrupting the process may possibly brick the module.
