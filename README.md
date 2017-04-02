# LiveFreeOrDICOM
DICOM to SQL DVH Database

This code is intended for Radiation Oncology departments to build a SQL database of DVH's from DICOM files (Plan, Structure, Dose).
This is a work in progress.  This file will eventually contain instructions for an end-user.

## Code organization
*DICOM_to_Python*  
This code contains functions that read dicom files and generate python objects containing the data required for input into the
SQL database.  There is no explicit user input.  All data is pulled from DICOM files (except for RxDose from Pinnacle, see note
in SQL Database format).

*SQL_Tools*  
This code handles all communication with SQL with MySQL Connector.  No DICOM files are used in this code and require the python objects
generated by DICOM_to_Python functions.

*DICOM_to_SQL*  
This has the simple objective of writing to SQL Database with only the starting path folder to begin a DICOM file search.

*Analysis_Tools*  
These functions are designed to process data retrieved from the SQL data and convert into python objects.

*ROI_Name_Manager*  
From independently created .roi files, this class generates a map of roi names and provides functions to query
and edit this map.  Each roi points to an institutional roi, physician roi, and a physician.

## To Do List

- [ ] Write DICOM pre-import validation function

- [ ] Add thorough comments throughout all code

- [ ] EUD calculations: Incorporate look-up tables of a-values

- [ ] Incorporate BED calculations

- [ ] Validate DoseToVolume and VolumeOfDose functions in Analysis_Tools

- [ ] Develop for SQL other than MySQL


## Dependencies
### Main Requirements:
* [Python](https://www.python.org) 2.7 tested
* [MySQL](https://dev.mysql.com/downloads/mysql/) and [MySQL Connector](https://dev.mysql.com/downloads/connector/python/)
* [numpy](https://pypi.python.org/pypi/numpy) 1.12.1 tested
* [matplotlib](https://pypi.python.org/pypi/matplotlib) 2.0.0 tested
* [pydicom](https://github.com/darcymason/pydicom) 0.9.9
* [dicompyler-core](https://pypi.python.org/pypi/dicompyler-core) 0.5.2
    * requirements per [developer](https://github.com/bastula)
        * [numpy](http://www.numpy.org/) 1.2 or higher
        * [pydicom](http://code.google.com/p/pydicom/) 0.9.9 or higher
            * pydicom 1.0 is preferred and can be installed via pip using: pip install https://github.com/darcymason/pydicom/archive/master.zip
        * [matplotlib](http://matplotlib.sourceforge.net/) 1.3.0 or higher (for DVH calculation)
        * [six](https://pythonhosted.org/six/) 1.5 or higher