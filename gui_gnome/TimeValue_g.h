/*
 *  TimeValue_g.h
 *  gnome
 *
 *  Created by Generic Programmer on 10/20/11.
 *  Copyright 2011 __MyCompanyName__. All rights reserved.
 *
 */

#ifndef __TimeValue_g__
#define __TimeValue_g__

#include "Earl.h"
#include "TypeDefs.h"
#include "TimeValue_b.h"
#include "ClassID_g.h"
class TTimeValue;
class TimeValue_g : virtual public TimeValue_b, virtual public ClassID_g {
	
public:
	virtual ClassID GetClassID () { return TYPE_TIMEVALUES; }
	virtual Boolean	IAm(ClassID id) { if(id==TYPE_TIMEVALUES) return TRUE; return ClassID_g::IAm(id); }
	virtual OSErr 	MakeClone(TTimeValue **clonePtrPtr);
	virtual OSErr 	BecomeClone(TTimeValue *clone);
	virtual OSErr	InitTimeFunc ();

	// I/O methods
	virtual OSErr 	Read  (BFPB *bfpb); // read from current position
	virtual OSErr 	Write (BFPB *bfpb); // write to  current position
	
	
};

#endif