### SQL Database format for this project
This code is being built assuming the database is MySQL.  There will be tables called Plans, DVHs, and beams in the database 'DVH'.
The 'Plans' table contains the following data:

Field | Type | Source
----- | ---- | ------
MRN | varchar(12) | RT_Plan.PatientID
Birthdate | date | RT_Plan.PatientBirthDate
Age | tinyint(3) unsigned | RT_Plan.PatientBirthdate & RT_Plan.StudyDate
Sex | char(1) | RT_Plan.PatientSex
SimStudyDate | date | RT_Plan.StudyDate
RadOnc | varchar(50) | RT_Plan.ReferringPhysicianName
TxSite | varchar(50) | RT_Plan.RTPlanLabel (i.e., Plan name)
RxDose | float | User input point dose or max dose from dicompylercore
Fractions | tinyint(3) unsigned | Sum of RT_Plan.FractionGroupSequence[].NumberOfFractionsPlanned
Energy | varchar(30) | RT_Plan.BeamSequence[].ControlPointSequence[0].NominalBeamEnergy
StudyInstanceUID | varchar(100) | RT_Plan.StudyInstanceUID
PatientOrientation | varchar(3) | RT_Plan.PatientSetupSequence[0].PatientPosition (e.g., HFS, FFP, etc.)
PlanTimeStamp | datetime | RT_Plan.RTPlanDate and RT_Plan.RTPlanTime
StTimeStamp | datetime | RT_St.StructureSetDate and RT_St.StructureSetTime
DoseTimeStamp | datetime | RT_Dose.ContentDate and RT_Dose.ContentTime
TPSManufacturer | varchar(50) | RT_Plan.Manufacturer
TPSSoftwareName | varchar(50) | RT_Plan.ManufactuerModelName
TPSSoftwareVersion | varchar(30) | RT_Plan.SoftwareVersions
TxModality | varchar(30) | dicompyler GetPlan(), RT_Plan.BeamSequence[0].ControlPointSequence[0], RT_Plan.ManufactuerModelName
MUs | int(6) unsigned | Sum of RT_Plan.FractionGroupSequence[FxGroup].ReferencedBeamSequence[BeamNum].BeamMeterset (linac only)
TxTime | time | TBD (Brachy and Gamma Knife only)

Pinnacle DICOM Dose files do not explicitly contain prescriptions or treatment sites.  This code requires that the plan name be equal to
the Tx Site.The prescription is parsed from a point stored in the DICOM RT Structure file with a name called 'rx: ' + [total dose] + 'Gy'
or 'rx: ' + [Fractsions] + ' x ' [FractionalDose] + 'Gy'. This point will have to be added by the user in their planning system prior to
DICOM export.  If this point is not found, the code will assume the Rx Dose is equal to the max point dose.


The 'Beams' table contains the following data:

Field | Type
----- | ----
MRN | varchar(12)
StudyInstanceUID | varchar(100)         
SimStudyDate | date                 
BeamNum | smallint(4) unsigned 
BeamDescription | varchar(30)          
FxGroup | smallint(4) unsigned 
Fractions | tinyint(3) unsigned  
NumFxGrpBeams | smallint(4) unsigned 
BeamDose | double unsigned      
BeamMUs | double unsigned      
RadiationType | varchar(30)          
BeamEnergy | float unsigned       
BeamType | varchar(30)          
ControlPoints | smallint(5) unsigned 
GantryStart | float                
GantryRotDir | varchar(3)           
GantryEnd | float                
ColAngle | double               
CouchAngle | double               
IsocenterCoord | varchar(30)          
SSD | double unsigned

The 'DVHs' table has one row per ROI and follows this format:

Field | Type
----- | ----
MRN | varchar(12)
StudyInstanceUID | varchar(100)
ROIName | varchar(50) 
Type | varchar(20) 
Volume | double      
MinDose | double      
MeanDose | double      
MaxDose | double      
DoseBinSize | float       
VolumeString | mediumtext


All doses are in Gy. All volumes are in cm^3. All data is populated from a combination of DICOM RT strucutre and dose files using
dicompyler and pydicom code.  VolumeString is a comma separated value string, when parsed generates a vector for the DVH y-values. 
The x-values are to be generated as a vector of equal length to the y-axis with equally spaced values based on the DoseBinSize (e.g., 
VolumeString = '100,100,90,50,20,0' and DoseBinSize = 1.0 then x-axis vector would equal [0.5 1.5 2.5 3.5 4.5 5.5]).
