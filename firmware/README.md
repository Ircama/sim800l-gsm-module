# Upgrading the SIM800L firmware with a Raspberry Pi

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

Ensure the SIM800L module is properly connected to the Raspberry Pi via serial interface.

Compile the code.

1418B06SIM800L24 is possibly the latest firmware for SIM800L. Enter the firmware directory and point to the ROM_VIVA file.

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

Remove the RST-GND short 10 seconds after the sync loop starts.

If Y is specified, the tool erases the FAT storage before flashing. The tool confirms erase completion via CMD_DL_BEGIN_RSP.

The firmware is split into 512-byte blocks. Each block is sent with a checksum for validation. Progress is displayed as a percentage. After transferring all data, the tool sends CMD_DL_END to finalize the process. The module reboots automatically (CMD_RUN_GSMSW command).

Serial Port Configuration: Baud Rate: 115200. Data Bits: 8, Stop Bits: 1, Parity: None

Warnings: interrupting the process may brick the module.
