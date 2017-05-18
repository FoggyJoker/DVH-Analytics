from SQL_to_Python import QuerySQL
from DVH_SQL import DVH_SQL
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dicompylercore import dicomparser
import os
import dicom


class Temp_DICOM_FileSet:
    def __init__(self):

        # Read SQL configuration file
        script_dir = os.path.dirname(__file__)
        rel_path = "preferences/import_settings.txt"
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path, 'r') as document:
            for line in document:
                line = line.split()
                if not line:
                    continue
                if line[0] == 'review':
                    start_path = line[1:][0]

        self.plan = []
        self.structure = []
        self.dose = []
        self.mrn = []

        f = []
        print str(datetime.now()), 'getting file list'
        for root, dirs, files in os.walk(start_path, topdown=False):
            for name in files:
                f.append(os.path.join(root, name))
        print str(datetime.now()), 'file list obtained'

        plan_files = []
        study_uid_plan = []
        structure_files = []
        study_uid_structure = []
        dose_files = []
        study_uid_dose = []
        mrns = []

        print str(datetime.now()), 'accumulating lists of plan, structure, and dose dicom files'
        for x in range(0, len(f)):
            try:
                dicom_file = dicom.read_file(f[x])
                if dicom_file.Modality.lower() == 'rtplan':
                    plan_files.append(f[x])
                    study_uid_plan.append(dicom_file.StudyInstanceUID)
                elif dicom_file.Modality.lower() == 'rtstruct':
                    structure_files.append(f[x])
                    study_uid_structure.append(dicom_file.StudyInstanceUID)
                elif dicom_file.Modality.lower() == 'rtdose':
                    dose_files.append(f[x])
                    study_uid_dose.append(dicom_file.StudyInstanceUID)
            except Exception:
                pass

        print str(datetime.now()), 'sorting files by uid'

        self.count = len(plan_files)

        for a in range(0, self.count):
            self.plan.append(plan_files[a])
            self.mrn.append(dicom.read_file(plan_files[a]).PatientID)
            for b in range(0, len(structure_files)):
                if study_uid_plan[a] == study_uid_structure[b]:
                    self.structure.append(structure_files[b])
            for c in range(0, len(dose_files)):
                if study_uid_plan[a] == study_uid_dose[c]:
                    self.dose.append(dose_files[c])

        if self.count == 0:
            self.plan.append('')
            self.mrn.append('')
            self.structure.append('')
            self.dose.append('')

        print str(datetime.now()), 'files sorted'

    def get_roi_names(self, mrn):

        structure_file = self.structure[self.mrn.index(mrn)]
        rt_st = dicomparser.DicomParser(structure_file)
        rt_structures = rt_st.GetStructures()

        roi = {}
        for key in rt_structures:
            if rt_structures[key]['type'].upper() not in {'MARKER', 'REGISTRATION', 'ISOCENTER'}:
                roi[key] = rt_structures[key]['name']

        return roi


def recalculate_ages():

    dvh_data = QuerySQL('Plans', "mrn != ''")
    cnx = DVH_SQL()

    for i in range(0, len(dvh_data.mrn)):
        uid = dvh_data.study_instance_uid[i]
        sim_study_date = dvh_data.sim_study_date[i].split('-')
        birth_date = dvh_data.birth_date[i].split('-')

        birth_year = int(birth_date[0])
        birth_month = int(birth_date[1])
        birth_day = int(birth_date[2])
        birth_date_obj = datetime.datetime(birth_year, birth_month, birth_day)

        sim_study_year = int(sim_study_date[0])
        sim_study_month = int(sim_study_date[1])
        sim_study_day = int(sim_study_date[2])
        sim_study_date_obj = datetime.datetime(sim_study_year,
                                               sim_study_month,
                                               sim_study_day)

        if sim_study_date == '1800-01-01':
            age = '(NULL)'
        else:
            age = relativedelta(sim_study_date_obj, birth_date_obj).years

        condition = "study_instance_uid = '" + uid + "'"
        cnx.update('Plans', 'age', str(age), condition)

    cnx.cnx.close()
