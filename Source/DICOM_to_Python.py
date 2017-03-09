#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 26 11:06:28 2017

@author: nightowl
"""

import dicom
from dicompylercore import dicomparser, dvhcalc
from datetime import datetime
from dateutil.relativedelta import relativedelta
from SQL_Tools import GetPlanIDs


class ROI:
    def __init__(self, MRN, PlanID, ROI_Name, Type, Volume, MinDose, MeanDose,
                 MaxDose, DoseBinSize, VolumeString):
        self.MRN = MRN
        self.PlanID = PlanID
        self.ROI_Name = ROI_Name
        self.Type = Type
        self.Volume = Volume
        self.MinDose = MinDose
        self.MeanDose = MeanDose
        self.MaxDose = MaxDose
        self.DoseBinSize = DoseBinSize
        self.VolumeString = VolumeString


class Plan:
    def __init__(self, MRN, PlanID, Birthdate, Age, Sex, SimStudyDate,
                 RadOnc, TxSite, RxDose, Fractions, Energy, StudyInstanceUID,
                 PatientOrientation, PlanTimeStamp, StTimeStamp, DoseTimeStamp,
                 TPSManufacturer, TPSSoftwareName, TPSSoftwareVersion,
                 TxModality, MUs, TxTime):
        self.MRN = MRN
        self.PlanID = PlanID
        self.Birthdate = Birthdate
        self.Age = Age
        self.Sex = Sex
        self.SimStudyDate = SimStudyDate
        self.RadOnc = RadOnc
        self.TxSite = TxSite
        self.RxDose = RxDose
        self.Fractions = Fractions
        self.Energy = Energy
        self.StudyInstanceUID = StudyInstanceUID
        self.PatientOrientation = PatientOrientation
        self.PlanTimeStamp = PlanTimeStamp
        self.StTimeStamp = StTimeStamp
        self.DoseTimeStamp = DoseTimeStamp
        self.TPSManufacturer = TPSManufacturer
        self.TPSSoftwareName = TPSSoftwareName
        self.TPSSoftwareVersion = TPSSoftwareVersion
        self.TxModality = TxModality
        self.MUs = MUs
        self.TxTime = TxTime


def Create_ROI_PyTable(StructureFile, DoseFile):
    # Import RT Structure and RT Dose files using dicompyler
    RT_St = dicomparser.DicomParser(StructureFile)
    RT_St_dicom = dicom.read_file(StructureFile)
    Structures = RT_St.GetStructures()
    ROI_Count = len(Structures)
    # ROI_Count = 10

    MRN = RT_St_dicom.PatientID
    PlanIDs = GetPlanIDs(MRN)
    PlanID = PlanIDs[PlanIDs.index(max(PlanIDs))][0]

    ROI_List = {}
    ROI_List_Counter = 1
    for ROI_Counter in range(1, ROI_Count):
        # Import DVH from RT Structure and RT Dose files
        if Structures[ROI_Counter]['type'] != 'MARKER':
            Current_DVH = dvhcalc.get_dvh(StructureFile, DoseFile, ROI_Counter)
            if Current_DVH.volume > 0:
                print('Importing ' + Current_DVH.name)
                Current_ROI = ROI(MRN,
                                  PlanID,
                                  Structures[ROI_Counter]['name'],
                                  Structures[ROI_Counter]['type'],
                                  Current_DVH.volume,
                                  Current_DVH.min,
                                  Current_DVH.mean,
                                  Current_DVH.max,
                                  Current_DVH.bins[1],
                                  ','.join(['%.2f' % num for num in Current_DVH.counts]))
                ROI_List[ROI_List_Counter] = Current_ROI
                ROI_List_Counter += 1
    return ROI_List


def Create_Plan_Py(PlanFile, StructureFile, DoseFile):
    # Import RT Dose files using dicompyler
    RT_Plan = dicom.read_file(PlanFile)
    RT_Plan_dicompyler = dicomparser.DicomParser(PlanFile)
    RT_Plan_Obj = RT_Plan_dicompyler.GetPlan()
    RT_St = dicom.read_file(StructureFile)
    RT_Dose = dicom.read_file(DoseFile)

    MRN = RT_Plan.PatientID

    PlanIDs = GetPlanIDs(MRN)
    if not PlanIDs:
        PlanID = 1
    else:
        PlanID = PlanIDs[PlanIDs.index(max(PlanIDs))][0] + 1

    BirthDate = RT_Plan.PatientBirthDate
    if not BirthDate:
        BirthDate = '18000101'
    BirthYear = int(BirthDate[0:4])
    BirthMonth = int(BirthDate[4:6])
    BirthDay = int(BirthDate[6:8])
    BirthDateObj = datetime(BirthYear, BirthMonth, BirthDay)

    Sex = RT_Plan.PatientSex
    if Sex == 'M':
        pass
    elif Sex == 'F':
        pass
    else:
        Sex = '-'

    SimStudyDate = RT_Plan.StudyDate
    SimStudyYear = int(SimStudyDate[0:4])
    SimStudyMonth = int(SimStudyDate[4:6])
    SimStudyDay = int(SimStudyDate[6:8])
    SimStudyDateObj = datetime(SimStudyYear, SimStudyMonth, SimStudyDay)

    Age = relativedelta(SimStudyDateObj, BirthDateObj).years

    RadOnc = RT_Plan.ReferringPhysicianName

    TxSite = RT_Plan.RTPlanLabel

    Fractions = 0
    MUs = 0
    for FxGroup in range(0, len(RT_Plan.FractionGroupSequence)):
        Fractions += RT_Plan.FractionGroupSequence[FxGroup].NumberOfFractionsPlanned
        for BeamNum in range(0, RT_Plan.FractionGroupSequence[FxGroup].NumberOfBeams):
            MUs += RT_Plan.FractionGroupSequence[FxGroup].ReferencedBeamSequence[BeamNum].BeamMeterset

    StudyInstanceUID = RT_Plan.StudyInstanceUID
    PatientOrientation = RT_Plan.PatientSetupSequence[0].PatientPosition

    PlanTimeStamp = RT_Plan.RTPlanDate + RT_Plan.RTPlanTime
    StTimeStamp = RT_St.StructureSetDate + RT_St.StructureSetTime
    DoseTimeStamp = RT_Dose.ContentDate + RT_Dose.ContentTime

    TPSManufacturer = RT_Plan.Manufacturer
    TPSSoftwareName = RT_Plan.ManufacturerModelName
    TPSSoftwareVersion = RT_Plan.SoftwareVersions[0]

    # Because DICOM does not contain Rx's explicitly, the user must create
    # a point in the RT Structure file called 'rx [total dose]'
    RxFound = 0
    ROI_Counter = 0
    ROI_Count = len(RT_St.StructureSetROISequence) - 1
    RxString = ''
    ROI_Seq = RT_St.StructureSetROISequence
    while (not RxFound) and (ROI_Counter < ROI_Count):
        if len(ROI_Seq[ROI_Counter].ROIName) > 2:
            if ROI_Seq[ROI_Counter].ROIName[0:2].lower() == 'rx':
                RxString = ROI_Seq[ROI_Counter].ROIName
                RxFound = 1
            else:
                ROI_Counter += 1
        else:
            ROI_Counter += 1
    if not RxString:
        RxDose = RT_Plan_Obj['rxdose']/100
    else:
        RxString = RxString.lower()
        RxString = RxString[3:RxString.rfind('gy')]
        while RxString[len(RxString)-1] == ' ':
            RxString = RxString[0:len(RxString)-1]
        RxDose = float(RxString[RxString.rfind(' '):len(RxString)])
        if RxString.find('x') == -1:
            RxDose = float(RxString[RxString.rfind(' '):len(RxString)])
        else:
            RxDose = float(RxString[RxString.rfind(' '):len(RxString)]) * Fractions

    # This assumes that Plans are either 100% Arc plans or 100% Static Angle
    TxModality = ''
    Energy = ' '
    Temp = ''
    if RT_Plan_Obj['brachy']:
        TxModality = 'Brachy '
    else:
        for BeamNum in range(0, len(RT_Plan.BeamSequence) - 1):
            Temp += RT_Plan.BeamSequence[BeamNum].RadiationType + ' '
            FirstCP = RT_Plan.BeamSequence[BeamNum].ControlPointSequence[0]
            if FirstCP.GantryRotationDirection in {'CW', 'CC'}:
                Temp += 'Arc '
            else:
                Temp += '3D '
            EnergyTemp = ' ' + str(FirstCP.NominalBeamEnergy)
            if RT_Plan.BeamSequence[BeamNum].RadiationType.lower() == 'photon':
                EnergyTemp += 'MV '
            elif RT_Plan.BeamSequence[BeamNum].RadiationType.lower() == 'proton':
                EnergyTemp += 'MeV '
            elif RT_Plan.BeamSequence[BeamNum].RadiationType.lower() == 'electron':
                EnergyTemp += 'MeV '
            if Energy.find(EnergyTemp) < 0:
                Energy += EnergyTemp
        Energy = Energy[1:len(Energy)-1]
        if Temp.lower().find('photon') > -1:
            if Temp.lower().find('photon arc') > -1:
                TxModality += 'Photon Arc '
            else:
                TxModality += 'Photon 3D '
        if Temp.lower().find('electron') > -1:
            if Temp.lower().find('electron arc') > -1:
                TxModality += 'Electron Arc '
            else:
                TxModality += 'Electron 3D '
        elif Temp.lower().find('proton') > -1:
            TxModality += 'Proton '
    TxModality = TxModality[0:len(TxModality)-1]

    # Will require a yet to be named function to determine this
    TxTime = 0

    Plan_Py = Plan(MRN, PlanID, BirthDate, Age, Sex, SimStudyDate,
                   RadOnc, TxSite, RxDose, Fractions, Energy, StudyInstanceUID,
                   PatientOrientation, PlanTimeStamp, StTimeStamp,
                   DoseTimeStamp, TPSManufacturer, TPSSoftwareName,
                   TPSSoftwareVersion, TxModality, MUs, TxTime)

    return Plan_Py

if __name__ == '__main__':
    pass
