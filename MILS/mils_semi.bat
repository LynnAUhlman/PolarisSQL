@echo off
cd /d C:\Scripts\Polaris\mils_semi

"C:\ProgramData\Miniconda3\condabin\conda.bat" run -n sic python "C:\Scripts\Polaris\mils_semi\mils_semiannual_report_loader.py" >> task_log.txt 2>&1
