#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Mar  9 18:48:19 2017

@author: nightowl
"""

import numpy as np
from SQL_Tools import Query_SQL


def SQL_DVH_to_Py(Cursor):

    MaxDVH_Length = 0
    for row in Cursor:
        temp = str(list(row)).split(',')
        if len(temp) > MaxDVH_Length:
            MaxDVH_Length = len(temp)

    DVHs = np.zeros([MaxDVH_Length, len(Cursor)])

    DVH_Counter = 0
    for row in Cursor:
        temp = str(list(row)).split(',')
        CurrentDVH = np.zeros(MaxDVH_Length)
        size = len(temp) - 1
        CurrentDVH[0] = float(temp[0][3:len(temp[0])-1])
        for y in range(1, size - 1):
            CurrentDVH[y] = float(temp[y])
        try:
            CurrentDVH[size] = float(temp[len(temp)-1][0:len(temp[len(temp)-1])-2])
        except Exception:
            CurrentDVH[size] = 0

        if max(CurrentDVH) > 0:
            CurrentDVH /= max(CurrentDVH)
        DVHs[:, DVH_Counter] = CurrentDVH
        DVH_Counter += 1

    return DVHs


def GetDVHsFromSQL(*ConditionStr):

    if ConditionStr:
        DVHs = Query_SQL('DVHs', 'VolumeString', ConditionStr[0])
    else:
        DVHs = Query_SQL('DVHs', 'VolumeString')
    DVHs = SQL_DVH_to_Py(DVHs)
    
    return DVHs


if __name__ == '__main__':
    pass
