/* A skeleton for an ingestion booster.
 */


#define HAVE_INT64_TIMESTAMP  // read this from <pg-config --includes>/c.h ?

#define _XOPEN_SOURCE
#define _ISOC99_SOURCE

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>
#include <assert.h>
#include <math.h>
#include <time.h>
#include <endian.h> 
#include <stdlib.h>
#include <errno.h>
#include <arpa/inet.h>
#include "boosterskel.h"

/* The following items should probably be collected in a parseContext */
char *context=NULL;  // handleInvalidRecord() looks here to give 
// more informative error messages
jmp_buf ignoreRecord; // longjmp target for non-letal bad records


/* Epoch of pq dumps.  Let's hope they don't change that frequently */
static struct tm pqEpochParts = {
	.tm_sec = 0,
	.tm_min = 0,
	.tm_hour = 0,
	.tm_mday = 1,
	.tm_mon = 0,
	.tm_year = 100,
	.tm_wday = -1,
	.tm_yday = -1,
	.tm_isdst = 0,
};
static time_t PqEpoch;

void die(char *format, ...)
{
	va_list ap;
	va_start(ap, format);
	(void)fprintf(stderr, "importbooster: ");
	(void)vfprintf(stderr, format, ap);
	va_end(ap);
	(void)fprintf(stderr, "\n");
	exit(1);
}

void handleBadRecord(char *format, ...)
{
	va_list ap;
	va_start(ap, format);
	(void)fprintf(stderr, "importbooster: ");
	if (context) {
		(void)fprintf(stderr, "Bad Record: '%s'\n", context);
	}
#ifndef IGNORE_BAD_RECORDS
	(void)vfprintf(stderr, format, ap);
	(void)fprintf(stderr, "\n");
	va_end(ap);
#else
	va_end(ap);
	longjmp(ignoreRecord, 1);
#endif
}


#define DATA_OUT(data, nbytes, destination) \
	fwrite(data, 1, nbytes, (FILE*)destination)


void
j2date(int jd, int *year, int *month, int *day)
{  /* jd -> ymd, lifted from postgresql source */
	unsigned int julian;
	unsigned int quad;
	unsigned int extra;
	int			y;

	julian = jd;
	julian += 32044;
	quad = julian / 146097;
	extra = (julian - quad * 146097) * 4 + 3;
	julian += 60 + quad * 3 + extra / 146097;
	quad = julian / 1461;
	julian -= quad * 1461;
	y = julian * 4 / 1461;
	julian = ((y != 0) ? ((julian + 305) % 365) : ((julian + 306) % 366))
		+ 123;
	y += quad * 4;
	*year = y - 4800;
	quad = julian * 2141 / 65536;
	*day = julian - 7834 * quad / 256;
	*month = (quad + 10) % 12 + 1;
	return;
}	/* j2date() */


int julian2unixtime(double julian, time_t *result)
{
	struct tm datetime;
	double hrs, mins;

	julian += 0.5;
	j2date((int)trunc(julian), &datetime.tm_year, &datetime.tm_mon,
		&datetime.tm_mday);
	datetime.tm_year -= 1900;  /* mktime wants it like this.  yuck. */
	datetime.tm_mon -= 1;
	hrs = (julian-trunc(julian))*24;
	datetime.tm_hour = (int)trunc(hrs);
	mins = (hrs-datetime.tm_hour)*60;
	datetime.tm_min = (int)trunc(mins);
	datetime.tm_sec = (int)trunc((mins-datetime.tm_min)*60);
	datetime.tm_isdst = 0;
	*result = mktime(&datetime);
	return 0;
}


void makeTimeFromJd(Field *field)
{ /* double field to date field */
	assert(field->type==VAL_DOUBLE);
	field->type = VAL_DATETIME;
	julian2unixtime(field->val.c_double, &(field->val.time));
}


double mjdToJYear(double mjd)
{
	return (mjd-51544.5)/365.25+2000;
}


void linearTransform(Field *field, double offset, double factor)
{
	switch (field->type) {
		case VAL_FLOAT:
			field->val.c_float = offset+field->val.c_float*factor;
			break;
		case VAL_DOUBLE:
			field->val.c_double = offset+field->val.c_double*factor;
			break;
		case VAL_INT:
			field->val.c_int32 = offset+field->val.c_int32*factor;
			break;
		default:
			/* should we raise error for other Non-NULL types? */
			break;
	}
}

void stripWhitespace(char *str)
{
	char *cp=str, *dp;

	while (*cp && isspace(*cp)) {
		cp++;
	}
	if (!*cp) {
		*str = 0;
		return;
	}
	for (dp=str; *cp;) {
		*dp++ = *cp++;
	}
	*dp-- = 0;
	while (isspace(*dp)) {
		*dp-- = 0;
	}
}

char* copyString(char *src, char *dest, int start, int len)
{
	strncpy(dest, src+start, len);
	dest[len] = 0;
	stripWhitespace(dest);
	if (!*dest) {
		return NULL;
	}
	return dest;
}


int isWhitespaceOnly(char *str)
{
	while (*str) {
		if (! isspace(*str++)) {
			return 0;
		}
	}
	return 1;
}


#define scanfWithWhitespace(input, format, field, expType) \
	if (1!=sscanf(input, format, (expType*)&(field->val))) { \
		if (!isWhitespaceOnly(input)) { \
			handleBadRecord("Invalid literal for %s: '%s'", STRINGIFY(expType), input); \
		} else { \
			field->type = VAL_NULL; \
		} \
	} 


void _parseWithMagicNULL(char *sscanfFormat, valType destType, char *src, 
	Field *field, int start, int len, char *magicVal)
{
	char input[len+1];

	copyString(src, input, start, len);
	if (!strcmp(input, magicVal)) {
		field->type = VAL_NULL;
		return;
	}
	field->type = destType;
	scanfWithWhitespace(input, sscanfFormat, field, float);
}


void parseFloatWithMagicNULL(char *src, Field *field, int start, int len,
		char *magicVal)
{
	_parseWithMagicNULL("%f", VAL_FLOAT, src, field, start, len, magicVal);
}


void parseDoubleWithMagicNULL(char *src, Field *field, int start, int len,
		char *magicVal)
{
	_parseWithMagicNULL("%lf", VAL_DOUBLE, src, field, start, len, magicVal);
}


void parseFloat(char *src, Field *field, int start, int len)
{
	char input[len+1];

	copyString(src, input, start, len);
	field->type = VAL_FLOAT;
	scanfWithWhitespace(input, "%f", field, float);
}

void parseDouble(char *src, Field *field, int start, int len)
{
	char input[len+1];

	copyString(src, input, start, len);
	field->type = VAL_DOUBLE;
	scanfWithWhitespace(input, "%lf", field, double);
}

void parseBigint(char *src, Field *field, int start, int len)
{
	char input[len+1];
	copyString(src, input, start, len);
	field->type = VAL_BIGINT;
	scanfWithWhitespace(input, "%Ld", field, int64_t);
}

void parseInt(char *src, Field *field, int start, int len)
{
	char input[len+1];

	copyString(src, input, start, len);
	field->type = VAL_INT;
	scanfWithWhitespace(input, "%d", field, int);
}

void parseShort(char *src, Field *field, int start, int len)
{
	char input[len+1];

	copyString(src, input, start, len);
	field->type = VAL_SHORT;
	scanfWithWhitespace(input, "%hd", field, short);
}


void parseBlankBoolean(char *src, Field *field, int srcInd)
{
	field->type = VAL_BOOL;

	if (isspace(src[srcInd])) {
		field->val.c_int8 = 0;
	} else {
		field->val.c_int8 = 1;
	}
}

void parseString(char *src, Field *field, int start, int len, char *space)
{
	copyString(src, space, start, len);
	field->length = len;
	field->type = VAL_TEXT;
	field->val.c_ptr = space;
}

void parseStringWithMagicNULL(char *src, Field *field, int start, 
	int len, char *space, char *magic)
{
	parseString(src, field, start, len, space);
	if (!strcmp(space, magic)) {
		field->type = VAL_NULL;
	}
}

void parseChar(char *src, Field *field, int srcInd)
{
	field->type = VAL_CHAR;
	if (isspace(src[srcInd])) {
		field->type = VAL_NULL;
	} else {
		field->val.c_int8 = src[srcInd];
	}
}

int sscanfWithNULL(char *source, char *format, Field *field, void *dest) {
	if (*source==0) { /* empty string, make thing NULL */
		field->type = VAL_NULL;
		return 1;
	}
	return sscanf(source, format, dest);
}
		
void real_fieldscanf(char *str, Field *f, valType type, char *fieldName, ...)
{
	int itemsMatched=1;
	va_list ap;

#ifdef AUTO_NULL
	if (!strcmp(str, STRINGIFY_VAL(AUTO_NULL))) {
		f->type = VAL_NULL;
		return;
	}
#endif
	va_start(ap, fieldName);
	f->type = type;
	switch (type) {
		case VAL_NULL:
			break;
		case VAL_BOOL:
			handleBadRecord("Can't fieldscanf bools at %s", fieldName);
			break;
		case VAL_CHAR:
			f->val.c_int8 = *str;
			break;
		case VAL_SHORT:
			itemsMatched = sscanfWithNULL(str, "%hd", f, &(f->val.c_int16));
			break;
		case VAL_INT:
			itemsMatched = sscanfWithNULL(str, "%d", f, &(f->val.c_int32));
			break;
		case VAL_FLOAT:
			itemsMatched = sscanfWithNULL(str, "%f", f, &(f->val.c_float));
			break;
		case VAL_DOUBLE:
			itemsMatched = sscanfWithNULL(str, "%lf", f, &(f->val.c_double));
			break;
		case VAL_BIGINT:
			itemsMatched = sscanfWithNULL(str, "%Ld", f, &(f->val.c_int64));
			break;
		case VAL_TEXT:
			f->val.c_ptr = str;
			break;
		case VAL_DATETIME:
		case VAL_DATE: {
			char *dateFormat = va_arg(ap, char*);
			struct tm timeParts;
			memset(&timeParts, 0, sizeof(struct tm));
			char *res = strptime(str, dateFormat, &timeParts);
			if (!res || *res) { /* strptime didn't consume string */
				itemsMatched = 0;
			} else {
				f->val.time = mktime(&timeParts);
			}}
			break;
		case VAL_JDATE: /* a julian day number to be dumped as a date */
			itemsMatched = sscanf(str, "%lf", &(f->val.c_double));
			break;
	}
	va_end(ap);
	if (itemsMatched!=1) {
		handleBadRecord("fieldscanf: Can't parse field %s (value '%s')", 
			fieldName, str);
	}
}



void writeHeader(void *destination)
{
	char *header = "PGCOPY\n\377\r\n\0";
	int32_t flags = 0;
	int32_t headerLength = 0;

	DATA_OUT(header, 11, destination);
	DATA_OUT(&flags, 4, destination);
	DATA_OUT(&headerLength, 4, destination);
}


void writeEndMarker(void *destination)
{
	int16_t endMarker = -1;

	endMarker = htons(endMarker);
	DATA_OUT(&endMarker, 2, destination);
}


void writeBoolean(Field *field, void *destination)
{
	char *head="\0\0\0\001";
	DATA_OUT(head, 4, destination);
	DATA_OUT(&(field->val.c_int8), 1, destination);
}

void writeShort(Field *field, void *destination)
{
	char *head="\0\0\0\002";
	uint16_t val=htons(field->val.c_int16);

	DATA_OUT(head, 4, destination);
	DATA_OUT(&val, 2, destination);
}

void writeInteger(Field *field, void *destination)
{
	char *head="\0\0\0\004";
	uint32_t val=htonl(field->val.c_int32);

	DATA_OUT(head, 4, destination);
	DATA_OUT(&val, 4, destination);
}


/* Complete insanity: Experimentally, it turns out that postgres wants
 * the floats in inverse byte sequence compared to what you get on
 * intel machines.  This isn't really defined by IEEE, so this might
 * not work for you.
 */
void mirrorBytes(char *mem, int numBytes)
{
	char *start = mem;
	char *end = mem+numBytes-1;

	if (__BYTE_ORDER==__BIG_ENDIAN) {
		return;
	}
	while (start<end) {
		char tmp=*start;
		*start++ = *end;
		*end-- = tmp;
	}
}

void writeBigint(Field *field, void *destination)
{
	uint32_t size=htonl(sizeof(int64_t));
	int64_t val=field->val.c_int64;

	mirrorBytes((char*)&val, sizeof(int64_t));
	DATA_OUT(&size, 4, destination);
	DATA_OUT(&val, sizeof(int64_t), destination);
}

void writeFloat(Field *field, void *destination)
{
	uint32_t size=htonl(sizeof(float));
	float val=field->val.c_float;

	mirrorBytes((char*)&val, sizeof(float));
	DATA_OUT(&size, 4, destination);
	DATA_OUT(&val, sizeof(float), destination);
}

void writeDouble(Field *field, void *destination)
{
	uint32_t size=htonl(sizeof(double));
	double val=field->val.c_double;

	mirrorBytes((char*)&val, sizeof(double));
	DATA_OUT(&size, 4, destination);
	DATA_OUT(&val, sizeof(double), destination);
}

void writeText(Field *field, void *destination)
{
	int len=strlen(field->val.c_ptr);
	uint32_t size=htonl(len);
	DATA_OUT(&size, 4, destination);
	DATA_OUT(field->val.c_ptr, len, destination);
}

double round(double val)
{
	return floor(val+0.5);
}

/* Pg's dump has the number of days since the epoch 2000-01-01 for dates.
 * 2451545.0 is noon UTC, 2001-01-01, the round adds 12 hours back and forth.
 */
void writeJdate(Field *field, void *destination)
{
	int32_t daysSinceEpoch=htonl(
		(int32_t)(round(field->val.c_double-2451545.0)));
	uint32_t size=htonl(sizeof(int32_t));
	
	DATA_OUT(&size, 4, destination);
	DATA_OUT(&daysSinceEpoch, sizeof(int32_t), destination);
}


void writeDate(Field *field, void *destination)
{
	/* field->time is a unix time_t */
	int32_t daysSinceEpoch=((field->val.time-PqEpoch)/86400);
	uint32_t data=htonl(daysSinceEpoch);
	uint32_t size=htonl(sizeof(int32_t));

/*	fprintf(stderr, "dse: %d\n", daysSinceEpoch);*/
	DATA_OUT(&size, 4, destination);
	DATA_OUT(&data, sizeof(uint32_t), destination);
}


void writeDatetime(Field *field, void *destination)
{ /* it seems postgres stores dates and times either in int64s or in
  something else :-).  Well, I take the int64 thing here, and there,
	I guess it's just the number of microseconds since the epoch. */
#ifdef HAVE_INT64_TIMESTAMP
	int64_t usecsSinceEpoch = (field->val.time-PqEpoch);
	uint32_t size = sizeof(int64_t);
	usecsSinceEpoch *= 1000000;
#else
	double usecsSinceEpoch = (field->val.time-PqEpoch);
	uint32_t size = sizeof(double);
#endif
	uint32_t size_n=htonl(size);

	mirrorBytes((char*)&usecsSinceEpoch, size);
	DATA_OUT(&size_n, 4, destination);
	DATA_OUT(&usecsSinceEpoch, size, destination);
}


void writeField(Field *field, void *destination)
{
	int32_t nullValue = htonl(-1);

	switch (field->type) {
		case VAL_NULL:
			DATA_OUT(&nullValue, 4, destination);
			break;
		case VAL_BOOL:
			writeBoolean(field, destination);
			break;
		case VAL_CHAR:
			writeBoolean(field, destination);
			break;
		case VAL_SHORT:
			writeShort(field, destination);
			break;
		case VAL_INT:
			writeInteger(field, destination);
			break;
		case VAL_BIGINT:
			writeBigint(field, destination);
			break;
		case VAL_FLOAT:
			writeFloat(field, destination);
			break;
		case VAL_DOUBLE:
			writeDouble(field, destination);
			break;
		case VAL_TEXT:
			writeText(field, destination);
			break;
		case VAL_JDATE:
			writeJdate(field, destination);
			break;
		case VAL_DATE:
			writeDate(field, destination);
			break;
		case VAL_DATETIME:
			writeDatetime(field, destination);
			break;
		default:
			die("Unknown type code: %d\n", field->type);
	}
}

void writeTuple(Field *fields, int numFields, void *destination)
{
	Field *curField;
	int16_t fieldCount=htons(numFields);
	
	DATA_OUT(&fieldCount, 2, destination);
	for (curField=fields; curField-fields<numFields; curField++) {
		writeField(curField, destination);
	}
}


int degToHms(double deg,
	int *hours_out, int *minutes_out, double *seconds_out)
{
	double rest, ipart;

	while (deg<0) {
		deg += 360;
	}
	rest = modf(deg/360.*24, &ipart);
	*hours_out = (int)ipart;
	rest = modf(rest*60, &ipart);
	*minutes_out = (int)ipart;
	*seconds_out = rest*60;
	return 0;
}


int degToDms(double deg, char *sign_out,
	int *degs_out, int *minutes_out, double *seconds_out)
{
	double rest, ipart;

	*sign_out = '+';
	if (deg<0) {
		*sign_out = '-';
		deg = -deg;
	}
	rest = modf(deg, &ipart);
	*degs_out = (int)ipart;
	rest = modf(rest*60, &ipart);
	*minutes_out = (int)ipart;
	*seconds_out = rest*60;
	return 0;
}


double jYearToJDN(double jYear)
{
	return (jYear-2000)*365.25+2451545.0;
}


char *strtok_u(char *arg, char *separator) {
/* like strtok, but doesn't merge adjacent separators */
	static char *cur;
	char *next, *res;

	if (arg!=NULL) {
		cur = arg;
	}
	next = strstr(cur, separator);
	if (next==NULL) {
		return NULL;
	}
	*next = 0;
	res = cur;
	cur = next+strlen(separator);
	return res;
}

int main(int argc, char **argv)
{
	PqEpoch = mktime(&pqEpochParts);
	createDumpfile(argc, argv);
	return 0;
}

