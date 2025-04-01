/* SIM800H/SIM800L download tool.
*
* Version  V1.01
* 2013-7-5
* Author:    Bill cheng
* Improved messages (Ircama)
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
#include<string.h>
#include <termios.h>
#include <sys/select.h>
#include <stdbool.h>

enum BOOL {FALSE = 0,TRUE = !FALSE};
int speed_arr[] = {B115200, B38400, B19200, B9600, B4800, B2400, B1200, B300,B38400, B19200, B9600, B4800, B2400, B1200, B300, };
int name_arr[] = {115200,38400,  19200,  9600,  4800,  2400,  1200,  300,38400,  19200,  9600, 4800, 2400, 1200,  300, };

#define   COMM_START_SYNC_CHAR       0xB5
#define   COMM_430_SYNC_CHAR         0x5B

#define	  COMM_HEX_ACK_CHAR				0x00

#define CMD_DL_BEGIN 		0x01
#define CMD_DL_BEGIN_FORMAT 0x81

#define CMD_DL_BEGIN_RSP 	0x02
#define CMD_DL_DATA		0x03
#define CMD_DL_DATA_RSP		0x04
#define CMD_DL_END		0x05
#define CMD_DL_END_RSP		0x06

#define CMD_RUN_GSMSW		0x07
#define CMD_RUN_GSMSW_RSP	0x08

#define CMD_DL_BEGIN_ERASE	0x09
#define CMD_DL_BEGIN_ERASE_ST	0x0A
#define CMD_DL_BEGIN_ERASE_EN   0x0B

static int com_fd;

void set_speed(int fd, int speed);
int set_Parity(int fd,int databits,int stopbits,int parity,int time);
int OpenDev(char *Dev);
void initcom(char *dev,int boad,int datelen, int stoplen,int parity);
int comm_init(char *dev);

void usage()
{
    printf("Usage: mtkdownload <com> ROM_VIVA <format>\n\n");
	printf("<com>: /dev/serial0,/dev/ttyS0,/dev/ttyS1,/dev/ttyS2..\n");
	printf("means  COM1,COM2,COM3,COM4,USB2COM\n");
	printf("ROM_VIVA is updating rom file\n");
	printf("<format> Y,N\n");
	printf("means  format FAT or not format Fat\n");
	printf("Example: mtkdownload /dev/serial0 ROM_VIVA Y\n");
}

unsigned char* prepare_write_buf(char *filename, unsigned int *len)
{
    unsigned char *write_buf = NULL;
    struct stat fs;

    int fd = open(filename, O_RDONLY);
    if(-1==fd)
    {
        perror("Cannot open file");
        return NULL;
    }
    if(-1==fstat(fd, &fs))
    {
        perror("Cannot get file size");
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
    if(4!=argc)
    {
        usage();
        return 1;
    }
    comm_init(argv[1]);
    initcom(argv[1],115200,8,1,'n');	//初始化串口，100代表usb转串口；

    unsigned int iRomlen = 0;

    unsigned char* romwrite_buf = prepare_write_buf(argv[2], &iRomlen);
    if(NULL==romwrite_buf) return 1;
    printf("Rom \r len=%d\t \n",iRomlen);
	int bFormat;

    if(!strcmp(argv[3],"Y"))
	bFormat=TRUE;
    else
	bFormat=FALSE;

    printf("Power On/Reset Target\n");
	//Get into SYNC 
    unsigned char RxBuffer[10];
    unsigned char TxBuffer[10];
    unsigned char RxxBuffer[100];
    int nrev=0;
    int nsend=0;

    /* Print version */
    printf("\nGet current firmware version:\n");
    usleep(100000);
    nsend = write(com_fd, "AT+CGMR\r\n", 9);
    if (nsend < 0) {
        perror("Write failed");
        return 1;
    }
    usleep(100000);
    nrev = read(com_fd, RxxBuffer, 99);  // Leave space for null terminator
    if (nrev < 0) {
        perror("Read failed");
        return 1;
    }
    RxxBuffer[nrev] = '\0';  // Ensure string termination
    printf("%.*s\n", nrev, RxxBuffer);  // Print only received bytes safely
    printf("Sleep for 10 seconds. Short RST to GND\n");
    usleep(10000000);
    printf("Remove the short after the sync loop starts (in 10 seconds). Should receive %x\n\n", COMM_START_SYNC_CHAR);
    usleep(10000000);

    /* Sync procedure */
    RxBuffer[0] = 0xFF;
    TxBuffer[0] = COMM_START_SYNC_CHAR;
    while (RxBuffer[0] != COMM_430_SYNC_CHAR)
    {
	// Send Sync Byte
		nsend=write(com_fd,TxBuffer,1);
        printf("\rSEND %d Byte \t%02x. ",nsend,TxBuffer[0]); 
		nrev = read(com_fd,RxBuffer,1);
        if (nrev)
            printf("recv  %d Byte \t%02x                                    ",nrev,RxBuffer[0]);
        else
            printf("No byte received. Release RST now!                  ");
    }
	//send cmd download begin 0x0001 and wait response

    unsigned int remain = iRomlen;
    unsigned int towrite;
	
    printf("\n\nStarting flash write\n");
	
    printf("Start to Erase flash!\n");
    printf("Please wait for flash erase finished!\n");
	//unsigned long lEraseStartAddress = iRomStartAddress;
	//unsigned long lEraseEndAddress = iVivaStartAddress + iVivalen;
	//printf("Erase \r startAddress=%04x\t endAddress=%04x\t \n",lEraseStartAddress,lEraseEndAddress);

	if(!bFormat)
		TxBuffer[0] = CMD_DL_BEGIN;
	else
		TxBuffer[0] = CMD_DL_BEGIN_FORMAT;
    	towrite=128;


	if (set_Parity(com_fd,8,1,'n',150)== FALSE)
	{
		printf("Set Parity Error\n");
		if(com_fd>0)
				close(com_fd);	
		exit(1);
	} 	
	
	nsend = write(com_fd,TxBuffer, 1);
	printf("SEND %d Bytes %02x\n",nsend,TxBuffer[0]); 
	//send 128 head
	if(towrite != write(com_fd,romwrite_buf+(iRomlen-remain), towrite))
    	{
          printf("write rom head failed\n");
		  if(com_fd>0)
				close(com_fd);	
          return 1;
    	}
        printf("SEND %d Bytes \n",towrite);
	remain-=towrite;
	//
	nrev = 0;
	RxBuffer[0] = 0;
	while (((RxBuffer[0] != CMD_DL_BEGIN_RSP)&&(RxBuffer[0] != 'P')&&(RxBuffer[0] != 'C'))||(nrev == 0)||(RxBuffer[0] == 'R'))
	{
			RxBuffer[0] = 0;
			nrev = read(com_fd,RxBuffer, 1);
			printf("%02x\t",RxBuffer[0]); 
	}
	if (RxBuffer[0] != CMD_DL_BEGIN_RSP)
	{
		   printf ("erase flash fail!\n");
		   if(com_fd>0)
				close(com_fd);	
		   return 1;
	}
	printf("reading erase\n");
	nrev = 0;
	int count;
	count=0;
	while (count != 2)
	{
		nrev = read(com_fd,RxBuffer, 1);
		if(nrev==1)
		   count++;
		printf("\nrecv  %d Byte \t%02x\n",nrev,RxBuffer[0]); 
	}
	
	//start send rom data
	nsend = 0;
	unsigned long checksum = 0;
	printf("Start to program ROM file to flash!\n");
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
	    //printf("SEND %d Bytes \t%02x\n",nsend,TxBuffer[0]); 
		//send rom data
            if(towrite != write(com_fd,romwrite_buf+(iRomlen-remain), towrite))
            {
                printf("write rom failed\n");
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
		//printf("SEND checksum %d Bytes \t%02x\n",nsend,TxBuffer[0]); 

		nrev = 0;
		RxBuffer[0] = 0;
		while ((RxBuffer[0] != CMD_DL_DATA_RSP)&&(RxBuffer[0] != 'P')&&(RxBuffer[0] != 'C') && (nrev != 1))
		{
			nrev = read(com_fd,RxBuffer, 1);
			//printf("recv %d Byte \t%02x\n",nrev,RxBuffer[0]); 
		}
		if (RxBuffer[0] != CMD_DL_DATA_RSP)
		{
		   printf ("Error: writing flash error!\n");
		   if(com_fd>0)
			close(com_fd);	
		   return 1;
		}	
        	remain-=towrite;
	        printf("\rRom %d\t %d bytes sent   ", (int)((iRomlen-remain)*100/iRomlen), (int)(iRomlen-remain));
        	fflush(stdout);
    }
    if(0==remain)
	printf("Rom send Done!\n");     
    //send dl end 
    TxBuffer[0] = CMD_DL_END;
    nsend = write(com_fd,TxBuffer, 1);
    printf("SEND %d Bytes \t0x%02x\n",nsend,TxBuffer[0]);
    nrev = 0;
    RxBuffer[0] = 0;
    nrev = read(com_fd,RxBuffer, 1);
    printf("recv %d Byte \t%02x\n",nrev,RxBuffer[0]); 
    //send restart option
    TxBuffer[0] = CMD_RUN_GSMSW;
    nsend = write(com_fd,TxBuffer, 1);
    printf("SEND %d Bytes \t0x%02x\n",nsend,TxBuffer[0]);
    nrev = 0;
    RxBuffer[0] = 0;
    nrev = read(com_fd,RxBuffer, 1);
    printf("recv %d Byte \t%02x\n",nrev,RxBuffer[0]);
    
    if(com_fd>0)
		close(com_fd);	
    return 0;

}

void initcom(char *dev,int boad,int datelen, int stoplen,int parity)
{
	
	com_fd = OpenDev(dev);
	if (com_fd>0)
		set_speed(com_fd,boad);
	else
	{
		printf("Can't Open Serial Port!\n");
		exit(0);
	}
	if (set_Parity(com_fd,datelen,stoplen,parity,1)== FALSE)
	{
		printf("Set Parity Error\n");
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
			fprintf(stderr,"Unsupported data size\n");		
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
			fprintf(stderr,"Unsupported parity\n");		
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
			fprintf(stderr,"Unsupported stop bits\n");
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
	int	fd = open( Dev, O_RDWR | O_NOCTTY | O_NDELAY );         //
	if (-1 == fd)		
	{ /*设置数据位数*/			
		perror("Can't Open Serial Port");
		return -1;
	}
	if(fcntl(fd, F_SETFL, 0)<0)
		printf("fcntl failed!\n");
	else
		printf("fcntl=%d\n",fcntl(fd, F_SETFL,0));
	if(isatty(STDIN_FILENO)==0)
		printf("standard input is not a terminal device\n");
	else
		printf("isatty success!\n");
	printf("fd-open=%d\n",fd);	//else	
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
        perror("open serial 0\n");
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
 
    printf("configure complete\n");
    
    if(tcsetattr(fd,TCSANOW,&opt) != 0)
    {
        perror("serial error");
        return -1;
    }
    printf("start send and receive data\n");

    close(fd);     
    return 0;
}
