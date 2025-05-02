# SIM800L GSM module Security Policy

The HTTPS support of the SIM800L GSM module is insecure and needs a special backend implementation supporting sockets with old SSLv3 encryption methods.

Interfacing web backends with HTTP GET/POST requests will send data in plaintext, which means that anyone can read/sniff them.

## Reporting a Security Bug

The way to report a security bug is to open an [issue](https://github.com/Ircama/sim800l-gsm-module/issues) including related information
(e.g., reproduction steps, version).
