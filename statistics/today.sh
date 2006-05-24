#! /bin/bash
#
# $Id$
#
# Copyright (C) 2004, 2006 by Martin Thorsen Ranang
#

if [ -z "$CONFPATH" ]; then
    CONFPATH=$HOME/statistics
fi

. $CONFPATH/general_config.sh

RESOLUTION=days
START=`date +%Y-%m-%d`
END=`date +%Y-%m-%d`
FNAME=today_$RESOLUTION

ttpd_analyze $LOGS \
    --restrict-to=$RESTRICTIONS \
    --resolution=$RESOLUTION \
    --from=$START --to=$END \
    > $EXPORT/$FNAME.txt

RESOLUTION=hours
FNAME=today_$RESOLUTION

ttpd_analyze $LOGS \
    --restrict-to=$RESTRICTIONS \
    --resolution=$RESOLUTION \
    --from=$START --to=$END \
    --chart=$EXPORT/graphics/$FNAME.png \
    > $EXPORT/$FNAME.txt
