#! /bin/bash
#
# $Id$
#
# Copyright (C) 2004 by Martin Thorsen Ranang
#

CONFPATH=$HOME/statistics

. $CONFPATH/general_config.sh

RESOLUTION=weeks
year=$((`date +%Y` - 1))
week=$((`date +%V` + 1))

if [ $week -gt 53 ]; then
    week=1;
    year=$(( $year + 1 ));
fi

WEEK=$year,$week
END=`date +%Y-%m-%d`
FNAME=last_52_weeks_$RESOLUTION

ttpd_analyze $LOGS \
    --restrict-to=interface=$INTERFACE,host=$HOST,trans_type=$TRANS_TYPE \
    --resolution=$RESOLUTION \
    --week=$WEEK \
    --to=$END \
    --chart=$EXPORT/graphics/$FNAME.png \
    > $EXPORT/$FNAME.txt

#RESOLUTION=days
#FNAME=last_52_weeks_$RESOLUTION

#ttpd_analyze $LOGS \
#    --restrict-to=interface=$INTERFACE,host=$HOST,trans_type=$TRANS_TYPE \
#    --resolution=$RESOLUTION \
#    --week=$WEEK \
#    --chart=$EXPORT/graphics/$FNAME.png \
#    > $EXPORT/$FNAME.txt
