import unittest
from core import screenshot_file_time,parse
from intake_policy import exclusion_reason
class IntakeTests(unittest.TestCase):
 def test_filename_capture_timestamp(self):
  self.assertEqual(screenshot_file_time('Print Screen 2026_10_02 08_37_27.png'),'2026-10-02T08:37:27')
  self.assertEqual(screenshot_file_time(r'W:\Varian\Transfer\TDS\H192905\PrintScreen\Print Screen 2026_10_09 08_11_00.png'),'2026-10-09T08:11:00')
  self.assertEqual(screenshot_file_time('TerminateTasks_20261008123559973_2026_10_08 12_36_05_021.png'),'2026-10-08T12:36:05.021')
  self.assertEqual(screenshot_file_time('TerminateTasks_20261008123559973.png'),'2026-10-08T12:35:59.973')
  self.assertEqual(screenshot_file_time('Print Screen 2026_99_02 08_37_27.png'),'')
  self.assertEqual(screenshot_file_time('screenshot.png'),'')
 def test_ocr_additional_codes_do_not_leak_into_date(self):
  row=parse('Id: 136011\nName: SPV.SW.BEAM.MotionAxisNotAtPlan\nDateTime: 29-Sep-2026 02:36:30 PM\nAdditional fault codes: 136011')
  self.assertEqual(row['service_date'],'29-Sep-2026 02:36:30 PM')
  self.assertEqual(row['fault_code'],'136011')
 def test_irrelevant_pdf_and_empty_screenshot_are_excluded(self):
  self.assertTrue(exclusion_reason({'kind':'reports','text':'PPG-HT-G product guide','sources':[{'path':'PPG-HT-G.pdf'}]}))
  self.assertTrue(exclusion_reason({'kind':'reports','text':'The parameter settings in this product guide','document_type':'PMP parameters','issue':'PMP parameters'}))
  self.assertTrue(exclusion_reason({'kind':'screenshots','text':'Treatment screen','issue':''}))
  self.assertTrue(exclusion_reason({'kind':'screenshots','issue':'No active faults'}))
 def test_actual_reports_and_manual_faults_without_codes_are_kept(self):
  report={'kind':'reports','text':'Work Order Information\nWork Order WO-004612326\nSubject Artifacts on conebeam\nClosure Summary Inspected imaging','work_order':'WO-004612326','issue':'Artifacts on conebeam'}
  self.assertEqual(exclusion_reason(report),'')
  self.assertEqual(exclusion_reason({'kind':'reports','text':'PMP CHECKLIST H192905 preventive maintenance parameters'}),'')
  self.assertEqual(exclusion_reason({'kind':'screenshots','document_type':'Therapist entry','issue':'Therapist observed a fault'}),'')
  self.assertEqual(exclusion_reason({'kind':'screenshots','fault_code':'420219'}),'')
if __name__=='__main__':unittest.main()
