/* SIM800H download tool.
*
* Version  V1.01
* 2013-7-5
* Author:    Bill cheng
* Improved by Ircama 2025-04-13
*             
* License:    GPL
*
*/

#include <stdio.h>
#include <stdlib.h>     /**/
#include <sys/types.h>  /**/
#include <sys/stat.h>   /**/

#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <termios.h>
#include <sys/select.h>
#include <stdbool.h>
#include <errno.h>

enum BOOL {FALSE = 0,TRUE = !FALSE};
int speed_arr[] = {B115200, B38400, B19200, B9600, B4800, B2400, B1200, B300,B38400, B19200, B9600, B4800, B2400, B1200, B300, };
int name_arr[] = {115200,38400,  19200,  9600,  4800,  2400,  1200,  300,38400,  19200,  9600, 4800, 2400, 1200,  300, };

// Synchronization Word Detection(0xB5)
#define   COMM_START_SYNC_CHAR       0xB5  // Sync byte PC->MODULE
#define   COMM_430_SYNC_CHAR         0x5B  // Sync byte confirm MODULE->PC

// Not used
#define	  COMM_HEX_ACK_CHAR				0x00

// Send Head Information(0x01/0x81)
#define CMD_DL_BEGIN 		0x01  // Send head no format information PC->MODULE
#define CMD_DL_BEGIN_FORMAT 0x81  // Send head format information PC->MODULE

#define CMD_DL_BEGIN_RSP 	0x02  // Head information confirm MODULE->PC

// Upgrade
#define CMD_DL_DATA		    0x03  // Send Upgrade data PC->MODULE
#define CMD_DL_DATA_RSP		0x04  // Return confirm 0x04
#define CMD_DL_END		    0x05  // Send the end of the download
#define CMD_DL_END_RSP		0x06  // Return confirm 0x06

// Reset
#define CMD_RUN_GSMSW		0x07  // reset module PC->MODULE
#define CMD_RUN_GSMSW_RSP	0x08  // Reset module confirm MODULE ->PC

// Not used
#define CMD_DL_BEGIN_ERASE	0x09
#define CMD_DL_BEGIN_ERASE_ST	0x0A
#define CMD_DL_BEGIN_ERASE_EN   0x0B

#define LINE_LENGTH 40

static int com_fd;
static int disable_netlight = FALSE;

void set_speed(int fd, int speed);
int set_Parity(int fd,int databits,int stopbits,int parity,int time);
int OpenDev(char *Dev);
void initcom(char *dev,int boad,int datelen, int stoplen,int parity);
int comm_init(char *dev);

int print_version(int disable_netlight, int com_fd) {
    int nrev=0;
    int nsend=0;
    char RxxBuffer[1000];
    const char *cmd;

    /* Print version */
    printf("\nCurrent firmware version:\n");
    usleep(100000);
    if (disable_netlight) {
        cmd = "AT+CNETLIGHT=0;&W;+CGMR;+CNETLIGHT?\r\n";
    } else {
        cmd = "AT+CGMR;+CNETLIGHT?\r\n";
    }
    nsend = write(com_fd, cmd, strlen(cmd));
    if (nsend < 0) {
        perror("Write failed");
        return 1;
    }
    for (int i=0;i<20;i++) {
        usleep(100000);  // 0.5 seconds
        nrev = read(com_fd, RxxBuffer, 999);  // Leave space for null terminator
        if ((nrev < 0) || (nrev > 990)) {
            perror("Read failed");
            return 1;
        }
        RxxBuffer[nrev] = '\0';  // Ensure string termination
        printf("%.*s", nrev, RxxBuffer);  // Print only received bytes safely
        if (strstr(RxxBuffer, "OK") != NULL) {
            break;  // Found "OK", terminate early
        }
    }
    printf("\n");
    return 0;
}

int write_sysfs(int log, const char *path, const char *value) {
    int fd = open(path, O_WRONLY);
    if (fd < 0) {
        if (log)
            fprintf(stderr, "Could not open '%s' for writing. %s\n", path, strerror(errno));
        return -1;
    }
    if (write(fd, value, strlen(value)) < 0) {
        if (log)
            fprintf(stderr, "Could not write %s to '%s'. %s\n", value, path, strerror(errno));
        close(fd);
        return -1;
    }
    close(fd);
    return 0;
}

int hard_reset(int log, int gpio) {
    char path[64];
    char gpio_str[4];
    int exported = 0;

    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/value", gpio);
    int fd = open(path, O_WRONLY);
    if (fd < 0) {
        // Export the GPIO
        snprintf(path, sizeof(path), "/sys/class/gpio/export");
        snprintf(gpio_str, sizeof(gpio_str), "%d", gpio);
        if (log)
            printf("Exporting GPIO %s to %s\n", gpio_str, path);
        if (write_sysfs(log, path, gpio_str) < 0) {
            perror("Failed to export GPIO");
            return -1;
        }
        exported = 1;
    }
    close(fd);

    // Wait 500ms
    usleep(500000);

    // Set direction to out
    if (log)
        printf("Setting direction\n");
    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/direction", gpio);
    if (write_sysfs(log, path, "out") < 0) {
        perror("Failed to set direction");
        return -1;
    }

    // Drive HIGH
    if (log)
        printf("Drive HIGH\n");
    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/value", gpio);
    write_sysfs(log, path, "1");

    // Drive LOW
    if (log)
        printf("Drive LOW\n");
    write_sysfs(log, path, "0");

    // Wait 300ms
    usleep(300000);

    // Drive HIGH again
    if (log)
        printf("Drive HIGH\n");
    write_sysfs(log, path, "1");

    // Unexport the GPIO
    if (exported) {
        if (log)
            printf("Unexporting GPIO %s to %s\n", gpio_str, path);
        snprintf(path, sizeof(path), "/sys/class/gpio/unexport");
        snprintf(gpio_str, sizeof(gpio_str), "%d", gpio);
        if (write_sysfs(log, path, gpio_str) < 0) {
            perror("Failed to unexport GPIO");
            return -1;
        }
    }

    return 1;
}

void usage()
{
    printf("Usage: mtkdownload <com> ROM_VIVA <format> [<port>]\n\n");
	printf("<com>: e.g., /dev/serial0, /dev/ttyS0, /dev/ttyS1, /dev/ttyS2...\n\n");
	printf("ROM_VIVA: name of the ROM file\n\n");
	printf("<format> can be Y=format FAT, S=like Y + disable netlight,\n");
	printf("         N=skip FAT formatting, T=dry run.\n\n");
	printf("<port> optional Raspberry Pi BCM port number for performing reset. If 0:\n\
no upgrade, only read fw version; if negative: same as 0, with device reset\n");
	printf("\n\
Examples:\n\
\n\
mtkdownload /dev/serial0 ROM_VIVA Y\n\
Ask manual reset of the device, format the storage, perform the upgrade.\n\
\n\
mtkdownload /dev/serial0 ROM_VIVA Y 24\n\
Auto reset the device through GPIO 24, format the storage, perform the\n\
upgrade. 24 means GPIO BCM 24, equivalent to pin 18.\n\
\n\
mtkdownload /dev/serial0 ROM_VIVA T 24\n\
Auto reset the device through GPIO 24, perform a dry run of the upgrade\n\
operation.\n\
\n\
mtkdownload /dev/serial0 ROM_VIVA Y 0\n\
No upgrade, just read the firmware version.\n\
\n\
mtkdownload /dev/serial0 ROM_VIVA Y -24\n\
No upgrade, just read the firmware version and reset the device via GPIO\n\
BCM 24.\n\n");
}

unsigned char* prepare_write_buf(char *filename, unsigned int *len)
{
    unsigned char *write_buf = NULL;
    struct stat fs;

    int fd = open(filename, O_RDONLY);
    if(-1==fd)
    {
        fprintf(stderr, "Cannot open file '%s': %s\n", filename, strerror(errno));
        return NULL;
    }
    if(-1==fstat(fd, &fs))
    {
        fprintf(stderr, "Cannot get file size of file '%s': %s\n", filename, strerror(errno));
        goto error;
    }
    write_buf = (unsigned char*)malloc(fs.st_size+1);
    if(NULL==write_buf)
    {
        perror("malloc failed");
        goto error;
    }

    if(fs.st_size != read(fd, write_buf, fs.st_size))
    {
        perror("Reading file failed");
        goto error;
    }

    printf("Filename : %s\n", filename);
    printf("Filesize : %d bytes\n", (int)fs.st_size);	
	
    *len = fs.st_size;
    return write_buf;

error:
    if(fd!=-1) close(fd);
    if(NULL!=write_buf) free(write_buf);
    fs.st_size = 0;
    return NULL;
  
}

int main(int argc, char *argv[])
{
    if (argc < 4)
    {
        usage();
        return 1;
    }
    comm_init(argv[1]);
    initcom(argv[1],115200,8,1,'n');  // Initialize the serial port; 100 indicates USB-to-serial

    unsigned int iRomlen = 0;

    unsigned char* romwrite_buf = prepare_write_buf(argv[2], &iRomlen);
    if(NULL==romwrite_buf) return 1;
    printf("ROM length %d bytes\n", iRomlen);
	int bFormat;
    int test_mode = FALSE;
    disable_netlight = FALSE;

    if (!strcmp(argv[3], "Y")) {
        bFormat = TRUE;
    } else if (!strcmp(argv[3], "S")) {
        bFormat = TRUE;
        disable_netlight = TRUE;
    } else if (!strcmp(argv[3], "N")) {
        bFormat = FALSE;
    } else if (!strcmp(argv[3], "T")) {
        printf("Dry-run mode.\n");
        test_mode = TRUE;
    } else {
        fprintf(stderr, "\nInvalid option for the <format> argument: must be Y, N or T.\n\n");
        return 1;
    }

    printf("Contacting the device.\n");
	//Get into SYNC 
    unsigned char RxBuffer[10];
    unsigned char TxBuffer[10];
    int nrev=0;
    int nsend=0;
    int terminate=0;

    if (print_version(FALSE, com_fd)) {
        return 1;
    }

    if (argc == 5) {
        int gpio = atoi(argv[4]);
        if (gpio == 0) {
            fprintf(stderr, "Terminating without reset and without upgrade.\n\n");
            return 1;
        }
        if (gpio < 0) {
            gpio=-gpio;
            terminate=1;
        }
        if (hard_reset(0, gpio) == 1) {
            printf("Hard reset of port %d complete.\n\n", gpio);
        } else {
            fprintf(stderr, "Hard reset of port %d failed.\n\n", gpio);
            return 1;
        }
        if (terminate)
            return 2;
    } else {
        printf("Short RST to GND. Remove the short after the sync loop starts. Should receive %x\n\n", COMM_START_SYNC_CHAR);
    }

    /* Sync procedure - Synchronization Word Detection(0xB5) */
    RxBuffer[0] = 0xFF;
    TxBuffer[0] = COMM_START_SYNC_CHAR;
    while (RxBuffer[0] != COMM_430_SYNC_CHAR)
    {
	// Send Sync Byte
		nsend=write(com_fd,TxBuffer,1);
        printf("\rSEND %d Byte %02x. ",nsend,TxBuffer[0]); 
		nrev = read(com_fd,RxBuffer,1);
        if (nrev) {
            //printf("                                                           \n");
            printf("RECV %d Byte %02x.                                           ", nrev,RxBuffer[0]);
        }
        else
            printf("No byte received. Release RST now! (Ctr C to terminate)");
    }

    unsigned int remain = iRomlen;
    unsigned int towrite;
    int count;
	
    // Entered in upgrade mode
    printf("\n\nDevice entered in upgrade mode.\n");

    if (test_mode)
        goto final_reboot;

    printf("Please wait for flash erase to finish.\n");
	//unsigned long lEraseStartAddress = iRomStartAddress;
	//unsigned long lEraseEndAddress = iVivaStartAddress + iVivalen;
	//printf("Erase \r startAddress=%04x\t endAddress=%04x\t \n",lEraseStartAddress,lEraseEndAddress);

	// Send Head Information(0x01/0x81)
    if(!bFormat)
		TxBuffer[0] = CMD_DL_BEGIN;  // send cmd download begin 0x0001 and wait response
	else
		TxBuffer[0] = CMD_DL_BEGIN_FORMAT;  // erase the file system of the module
    	towrite=128;


	if (set_Parity(com_fd,8,1,'n',150)== FALSE)
	{
		fprintf(stderr, "Set Parity Error\n");
		if(com_fd>0)
				close(com_fd);	
		exit(1);
	} 	
	
	nsend = write(com_fd,TxBuffer, 1);
	printf("SEND %d Byte %02x\n", nsend, TxBuffer[0]); 
	//send 128 file head
	if(towrite != write(com_fd,romwrite_buf+(iRomlen-remain), towrite))
    	{
          fprintf(stderr, "write ROM head failed\n\n");
		  if(com_fd>0)
				close(com_fd);	
          return 1;
    	}
        printf("SEND %d Bytes, please wait erasure ('R' sequence) to complete with '02'...\n", towrite);
	remain-=towrite;
	//
	nrev = 0;
	RxBuffer[0] = 0;
    // 'P' = Write flash fail MODULE->PC
    // 'C' = Checksum error MODULE->PC
    // 'R' = Erasing MODULE->PC
    count = 0;
    printf("[ ");  // Opening structure
	while ((RxBuffer[0] != CMD_DL_BEGIN_RSP)||(nrev == 0)||(RxBuffer[0] == 'R'))
	{
			RxBuffer[0] = 0;
			nrev = read(com_fd,RxBuffer, 1);
            if (nrev != 1) {
                printf("\n\n");
                fprintf(stderr, "Erasure failed\n\n");
            }
            if (RxBuffer[0] < 33)
                printf("%02x ",RxBuffer[0]);
            else
                printf("%c ",RxBuffer[0]);
            count++;
            if (count % LINE_LENGTH == 0)
                printf("]\n[ ");

            if (RxBuffer[0] == 'P') {
                printf("]\n\n");
                fprintf(stderr, "Write flash failed.\n\n");
                return 1;
            }
            if (RxBuffer[0] == 'C') {
                printf("{Checksum error} ");
            }
            if (RxBuffer[0] == 'E') {
                printf("]\n\n");
                fprintf(stderr, "Erase error.\n\n");
                return 1;
            }
            if (RxBuffer[0] == 'S') {
                printf("]\n\n");
                fprintf(stderr, "File size error.\n\n");
                return 1;
            }
            if (RxBuffer[0] == 'M') {
                printf("]\n\n");
                fprintf(stderr, "Command error.\n\n");
                return 1;
            }
            if (RxBuffer[0] == 'T') {
                printf("{Timeout} ");
            }
            if (RxBuffer[0] == 'N') {
                printf("]\n\n");
                fprintf(stderr, "Data package num error.\n\n");
                return 1;
            }
            if (RxBuffer[0] == 'F') {
                printf("]\n\n");
                fprintf(stderr, "Time out between two commands.\n\n");
                return 1;
            }
	}
    if (count % LINE_LENGTH == 0) {
        printf("\r");  // Reset open bracket
    }
    else {
        printf("]\n");  // Closing structure
    }

	if (RxBuffer[0] != CMD_DL_BEGIN_RSP)
	{
        fprintf(stderr, "\nErase flash failed!\n\n");
        if(com_fd>0)
            close(com_fd);
        return 1;
	}
	printf("\nErase done. Reading the subsequent two bytes (maximum packet length 0x00, 0x08).\n");
	nrev = 0;
	count=0;
	while (count != 2)
	{
		nrev = read(com_fd,RxBuffer, 1);
		if(nrev==1)
		   count++;
		printf("RECV  %d Byte \t0x%02x\n",nrev,RxBuffer[0]); 
	}

    // Start sending ROM data
	nsend = 0;
	unsigned long checksum = 0;
	printf("\nUploading ROM_VIVA File to the module.\n");
	while(remain)
        {
       	    towrite = remain>0x200 ? 0x200 : remain;
            //send block size
            TxBuffer[0] = CMD_DL_DATA;
	    TxBuffer[1] = towrite & 0xFF;
	    TxBuffer[2] = (towrite >> 8) & 0xFF;
	    TxBuffer[3] = (towrite >> 16) & 0xFF;
	    TxBuffer[4] = (towrite >> 24) & 0xFF;
	    nsend = write(com_fd,TxBuffer, 5);
	    //printf("SEND %d Byte \t0x%02x\n",nsend,TxBuffer[0]); 
		//send rom data
            if(towrite != write(com_fd,romwrite_buf+(iRomlen-remain), towrite))
            {
                fprintf(stderr, "write ROM failed\n");
				if(com_fd>0)
					close(com_fd);	
                return 1;
            }
		//cal checksum and send
		checksum= 0;
		unsigned char *pBuf=romwrite_buf+(iRomlen-remain);
		for (count = 0;count <towrite;count++)
		{
			checksum += pBuf[count];
		}

		TxBuffer[0] = (unsigned char)(checksum & 0xFF);
		TxBuffer[1] = (unsigned char)((checksum >> 8) & 0xFF);
		TxBuffer[2] = (unsigned char)((checksum >> 16) & 0xFF);
		TxBuffer[3] = (unsigned char)((checksum >> 24) & 0xFF);
		nsend = write(com_fd,TxBuffer, 4);
		//printf("SEND checksum %d Byte \t0x%02x\n",nsend,TxBuffer[0]); 

		nrev = 0;
		RxBuffer[0] = 0;
		while ((RxBuffer[0] != CMD_DL_DATA_RSP)&&(RxBuffer[0] != 'P')&&(RxBuffer[0] != 'C') && (nrev != 1))
		{
			nrev = read(com_fd,RxBuffer, 1);
			//printf("recv %d Byte \t0x%02x\n",nrev,RxBuffer[0]); 
		}
		if (RxBuffer[0] != CMD_DL_DATA_RSP)
		{
		   fprintf(stderr, "Error: writing flash error!\n");
		   if(com_fd>0)
			close(com_fd);	
		   return 1;
		}	
        	remain-=towrite;
	        printf("\rROM %d\t %d bytes sent.   ", (int)((iRomlen-remain)*100/iRomlen), (int)(iRomlen-remain));
        	fflush(stdout);
    }
    if(0==remain)
        printf("ROM upload completed!\n");
    else {
        fprintf(stderr, "ROM upload NOT completed: remaining %d bytes.\n", remain);
        return 1;
    }

    // Send download end 
    TxBuffer[0] = CMD_DL_END;
    nsend = write(com_fd,TxBuffer, 1);
    printf("SEND 'Update end': \t\t%d Byte \t0x%02x\n",nsend,TxBuffer[0]);
    nrev = 0;
    RxBuffer[0] = 0;
    nrev = read(com_fd,RxBuffer, 1);
    printf("RECV 'Update end' resp: \t%d Byte \t0x%02x\n",nrev,RxBuffer[0]); 
    if ((nrev == 1) && (RxBuffer[0] == 'M')) {
        fprintf(stderr, "Command error received!\n\n");
        return 1;
    } else if ((nrev != 1) || (RxBuffer[0] != CMD_DL_END_RSP)) {
        fprintf(stderr, "Improper 'update end' response received!\n\n");
        return 1;
    }

    final_reboot:

        // Send restart option
        TxBuffer[0] = CMD_RUN_GSMSW;
        nsend = write(com_fd,TxBuffer, 1);
        printf("SEND 'Restart' \t\t\t%d Byte \t0x%02x\n",nsend,TxBuffer[0]);
        nrev = 0;
        RxBuffer[0] = 0;
        nrev = read(com_fd,RxBuffer, 1);

        printf("RECV 'restart' resp: \t\t%d Byte \t0x%02x\n",nrev,RxBuffer[0]);
        if ((nrev == 1) && (RxBuffer[0] == 'M')) {
            printf("'M' ('Command error') received. Flushing 'M' characters, please wait for about 30 seconds...\n");

            // Loop to skip all subsequent 'M' characters
            while (nrev == 1 && RxBuffer[0] == 'M') {
                nrev = read(com_fd, RxBuffer, 1);
            }

        } else if ((nrev != 1) || (RxBuffer[0] != CMD_RUN_GSMSW_RSP)) {
            fprintf(stderr, "Improper 'restart' response received!\n\n");
            return 1;
        }
        
        printf("Operation completed. Sleep for 5 seconds...\n");
        usleep(5000000);
        if (print_version(disable_netlight, com_fd)) {
            return 1;
        }

        if(com_fd>0) {
            close(com_fd);
            return 0;
        }
        return 1;

}  // of main

void initcom(char *dev,int boad,int datelen, int stoplen,int parity)
{
	
	com_fd = OpenDev(dev);
	if (com_fd>0)
		set_speed(com_fd,boad);
	else
	{
		fprintf(stderr, "Can't Open Serial Port!\n");
		exit(0);
	}
	if (set_Parity(com_fd,datelen,stoplen,parity,1)== FALSE)
	{
		fprintf(stderr, "Set Parity Error\n");
		exit(1);
	}
}

void set_speed(int fd, int speed)
{

  int   i, j=sizeof(speed_arr) / sizeof(int);
  int   status;
  struct termios   Opt;
  tcgetattr(fd, &Opt);

  for ( i= 0;  i < j;  i++)
  {
   	
	if  (speed == name_arr[i])
	{	
   	    
			tcflush(fd, TCIOFLUSH);
    	
			cfsetispeed(&Opt, speed_arr[i]);
    	
			cfsetospeed(&Opt, speed_arr[i]);
    	
			status = tcsetattr(fd, TCSANOW, &Opt);
    	
			if  (status != 0)
            
				perror("tcsetattr fd1");
     	
			return;
     	
		}
   
		tcflush(fd,TCIOFLUSH);
  
	}

}

/**
*@brief   设置串口数据位，停止位和效验位
*@param  fd 类型  int  打开的串口文件句柄*
*@param  databits 类型  int 数据位   取值 为 7 或者8*
*@param  stopbits 类型  int 停止位   取值为 1 或者2*
*@param  parity   类型  int  效验类型 取值为N,E,O,,S
*/
int set_Parity(int fd,int databits,int stopbits,int parity,int time)
{	
	struct termios options; 
	if  ( tcgetattr( fd,&options)  !=  0)  
	{
  	
		perror("SetupSerial 1");  	
		return(FALSE);  
	}  
	options.c_cflag &= ~CSIZE;  
	switch (databits) /*设置数据位数*/ 
	{
  		case 7:  		
			options.c_cflag |= CS7;  		
			break;  	
		case 8:		
			options.c_cflag |= CS8;		
			break;	
		default:		
			fprintf(stderr, "Unsupported data size\n");		
			return (FALSE);	
	}  
	switch (parity)  	
	{  	
		case 'n':	
		case 'N':		
			options.c_cflag &= ~PARENB;   /* Clear parity enable */		
			options.c_iflag &= ~INPCK;     /* Enable parity checking */		
			break;	
		case 'o':
		case 'O':
			options.c_cflag |= (PARODD | PARENB);  /* 设置为奇效验*/ 		
			options.c_iflag |= INPCK;             /* Disnable parity checking */		
			break;	
		case 'e':
		case 'E':		
			options.c_cflag |= PARENB;     /* Enable parity */		
			options.c_cflag &= ~PARODD;   /* 转换为偶效验*/		
			options.c_iflag |= INPCK;       /* Disnable parity checking */		
			break;	
		case 'S':
		case 's':  /*as no parity*/		
			options.c_cflag &= ~PARENB;		
			options.c_cflag &= ~CSTOPB;		
			break;	
		default:		
			fprintf(stderr, "Unsupported parity\n");		
			return (FALSE);		
	}
	/* 设置停止位*/  
	switch (stopbits)  	
	{  	
		case 1:		
			options.c_cflag &= ~CSTOPB;		
			break;	
		case 2:		
			options.c_cflag |= CSTOPB;		
			break;	
		default:
			fprintf(stderr, "Unsupported stop bits\n");
			return (FALSE);
	
	} 
	/* Set input parity option */  
	if (parity != 'n')  	
		options.c_iflag |= INPCK;	
	options.c_cc[VTIME] = time; // 0.1 seconds   
	options.c_cc[VMIN] = 0;  
	//options.c_cflag &= ~CRTSCTS; //~CNEW_RTSCTS;

	tcflush(fd,TCIFLUSH); /* Update the options and do it NOW */  
	if (tcsetattr(fd,TCSANOW,&options) != 0)  	
	{  		
		perror("SetupSerial 3");
		return (FALSE);	
	}  
	return (TRUE); 
}
/**
*@breif 打开串口
*/

int OpenDev(char *Dev)
{	
	int	fd = open(Dev, O_RDWR | O_NOCTTY | O_NDELAY );         //
	if (-1 == fd)		
	{ /*设置数据位数*/
        fprintf(stderr, "Cannot open serial port '%s': %s\n", Dev, strerror(errno));
		return -1;
	}
	if(fcntl(fd, F_SETFL, 0)<0)
		fprintf(stderr, "fcntl failed!\n");
	else
		printf("Clear all terminal serial port status bits succeeded (returned %d).\n",fcntl(fd, F_SETFL,0));
	if(isatty(STDIN_FILENO)==0)
		printf("standard input is not a terminal device.\n");
	else
		printf("Port is a tty (valid device).\n");
	//printf("fd-open=%d\n",fd);	//else	
	return fd;
}

int comm_init(char *dev)
{
    int fd;
    //int i; //Seems unused (CRImier)
    //int len; //Seems unused (CRImier)
    //int n = 0; //Seems unused (CRImier)
    //unsigned char read_buf[26]={'\0'}; //Seems unused (CRImier)
    //unsigned char write_buf[26]={'\0'};  //Seems unused (CRImier)
    struct termios opt; 
    
    fd = open(dev, O_RDWR | O_NOCTTY | O_NDELAY);    //默认为阻塞读方式
    if(fd == -1)
    {
        fprintf(stderr, "Cannot open serial port '%s': %s\n", dev, strerror(errno));
        exit(0);
    }

    tcgetattr(fd, &opt);      
    cfsetispeed(&opt, B115200);
    cfsetospeed(&opt, B115200);
    
    if(tcsetattr(fd,TCSANOW,&opt) != 0 )
    {     
       perror("tcsetattr error");
       return -1;
    }
    
    opt.c_cflag &= ~CSIZE;  
    opt.c_cflag |= CS8;   
    opt.c_cflag &= ~CSTOPB;
    opt.c_cflag &= ~PARENB; 
    opt.c_cflag &= ~INPCK;
    opt.c_cflag |= (CLOCAL|CREAD);
 
    opt.c_lflag &= ~(ICANON|ECHO|ECHOE|ISIG);
 
    opt.c_oflag &= ~OPOST;
    opt.c_oflag &= ~(ONLCR|OCRNL);
 
    opt.c_iflag &= ~(ICRNL|INLCR);
    opt.c_iflag &= ~(IXON|IXOFF|IXANY);
    
    opt.c_cc[VTIME] = 0;
    opt.c_cc[VMIN] = 0;
    
    tcflush(fd, TCIOFLUSH);
 
    printf("Tty serial port configuration completed.\n");
    
    if(tcsetattr(fd,TCSANOW,&opt) != 0)
    {
        perror("serial error");
        return -1;
    }
    printf("Ready to send and receive data.\n");

    close(fd);     
    return 0;
}
