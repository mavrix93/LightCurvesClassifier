#ifndef BOOSTERSKEL_H
#define BOOSTERSKEL_H

#define _XOPEN_SOURCE
#include <time.h>
#include <stdint.h>  /* for typedefs */
#include <setjmp.h>

#define DEGTORAD(x) ((x)/360.*2*M_PI)
#define F(x) (vals+x)

typedef enum valType_e {
	VAL_NULL,
	VAL_BOOL,
	VAL_CHAR,
	VAL_SHORT,
	VAL_INT,
	VAL_BIGINT,
	VAL_FLOAT,
	VAL_DOUBLE,
	VAL_TEXT,
	VAL_JDATE,  /* a julian year ("J2000.0"); this is stored as a simple double */
	VAL_DATE,   /* date expressed as a time_t */
	VAL_DATETIME, /* date and time expressed as a time_t */
} valType;

#define STRINGIFY(x) #x
#define STRINGIFY_VAL(arg) STRINGIFY(arg)

typedef struct Field_s {
	valType type;
	int length; /* ignored for anything but VAL_TEXT */
	union {
		char *c_ptr;
		double c_double;
		float c_float;
		int64_t c_int64;
		int32_t c_int32;
		int16_t c_int16;
		int8_t c_int8;
		time_t time;
	} val;
} Field;


#define MAKE_NULL(fi) F(fi)->type=VAL_NULL
#define MAKE_DOUBLE(fi, value) {\
	F(fi)->type=VAL_DOUBLE; F(fi)->val.c_double = value;}
#define MAKE_FLOAT(fi, value) {\
	F(fi)->type=VAL_FLOAT; F(fi)->val.c_float = value;}
#define MAKE_SHORT(fi, value) {\
	F(fi)->type=VAL_SHORT; F(fi)->val.c_int16 = value;}
#define MAKE_INT(fi, value) {\
	F(fi)->type=VAL_INT; F(fi)->val.c_int32 = value;}
#define MAKE_BIGINT(fi, value) {\
	F(fi)->type=VAL_BIGINT; F(fi)->val.c_int64 = value;}
#define MAKE_CHAR(fi, value) {\
	F(fi)->type=VAL_CHAR; F(fi)->val.c_int8 = value;}
#define MAKE_BYTE(fi, value) {\
	F(fi)->type=VAL_CHAR; F(fi)->val.c_int8 = value;}
#define MAKE_CHAR_NULL(fi, value, nullvalue) {\
	if ((value)==(nullvalue)) { MAKE_NULL(fi); } else {MAKE_CHAR(fi, value);}}
#define MAKE_JDATE(fi, value) {\
	F(fi)->type=VAL_JDATE; F(fi)->val.c_double = value;}
#define MAKE_TEXT(fi, value) {\
	F(fi)->type=VAL_TEXT; F(fi)->val.c_ptr = value;}

#define MAKE_WITH_NULL(type, fi, value, nullvalue) {\
	if ((value)==(nullvalue)) { MAKE_NULL(fi); } else {\
		MAKE_##type(fi, value);}}

#define AS2DEG(field) linearTransform(F(field), 0, 1/3600.)
#define MAS2DEG(field) linearTransform(F(field), 0, 1/3600./1000.)

#define fieldscanf(str, fieldName, type, ...) \
	real_fieldscanf((str), vals+(fieldName), type, STRINGIFY(fieldName),\
		## __VA_ARGS__)

void die(char *format, ...);
void linearTransform(Field *field, double offset, double factor);
int julian2unixtime(double julian, time_t *result);
double mjdToJYear(double mjd);
void makeTimeFromJd(Field *field);
void stripWhitespace(char *str);
char* copyString(char *src, char *dest, int start, int len);
int isWhitespaceOnly(char *str);
void parseFloat(char *src, Field *field, int start, int len);
void parseFloatWithMagicNULL(char *src, Field *field, int start, int len,
		char *magicVal);
void parseDoubleWithMagicNULL(char *src, Field *field, int start, int len,
		char *magicVal);
void parseDouble(char *src, Field *field, int start, int len);
void parseInt(char *src, Field *field, int start, int len);
void parseBigint(char *src, Field *field, int start, int len);
void parseShort(char *src, Field *field, int start, int len);
void parseBlankBoolean(char *src, Field *field, int srcInd);
void parseString(char *src, Field *field, int start, int len, char *space);
void parseStringWithMagicNull(char *src, Field *field, int start, int len, 
	char *space, char *magic);
void parseChar(char *src, Field *field, int srcInd);
void real_fieldscanf(char *str, Field *f, valType type, char *fieldName, ...);

int degToDms(double deg, char *sign_out,
	int *degs_out, int *minutes_out, double *seconds_out);
int degToHms(double deg, 
	int *hours_out, int *minutes_out, double *seconds_out);
double jYearToJDN(double jYear);

char *strtok_u(char *arg, char *separator);

// functions for creating dump files
void writeHeader(void *destination);
void handleBadRecord(char *format, ...);
void createDumpfile(int argc, char **argv);
void writeTuple(Field *fields, int numFields, void *destination);
void writeEndMarker(void *destination);

extern char *context; // handleInvalidRecord() looks here to give 
// more informative error messages

extern jmp_buf ignoreRecord; // longjmp target for non-letal bad records

#endif
