@echo off
cd /d C:\Scripts\Polaris\mils_monthly

"C:\ProgramData\Miniconda3\condabin\conda.bat" run -n sic python "C:\Scripts\Polaris\mils_monthly\mils_monthly_loader.py" >> task_log.txt 2>&1
