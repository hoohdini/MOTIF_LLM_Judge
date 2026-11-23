@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PY=.venv\Scripts\python.exe
set LOG=reports\regen1_run.log
if not exist reports mkdir reports
echo ==== %date% %time% start > %LOG%

echo [1/4] git: switch to regen/round1
git fetch origin >> %LOG% 2>&1
git checkout regen/round1 >> %LOG% 2>&1
git pull >> %LOG% 2>&1
git log --oneline -1 >> %LOG% 2>&1
if not exist data_in\a8\items_round1.jsonl (
  echo   FAILED: branch not switched. See %LOG%
  goto :end
)

for %%G in (a8 b7) do call :bundle %%G
for %%G in (a8 b7) do call :answers %%G
goto :end

:bundle
echo [%1] ingest + item audit (regen items only)
echo ==== [%1] >> %LOG%
%PY% run.py --store store_%1 ingest items data_in\%1\items_round1.jsonl --label "regen round1" >> %LOG% 2>&1
%PY% run.py --store store_%1 run --stage item --only ids\%1_regen1.ids.txt --workers 4 >> %LOG% 2>&1
echo [%1] retry failed calls (if any)
%PY% run.py --store store_%1 run --stage item --only ids\%1_regen1.ids.txt --workers 4 >> %LOG% 2>&1
%PY% run.py --store store_%1 decide --stage item >> %LOG% 2>&1
%PY% run.py --store store_%1 release build %1-v3 --note "regen round1" >> %LOG% 2>&1
%PY% analysis\weekend_report.py --store store_%1 --only ids\%1_regen1.ids.txt --out reports\%1_regen1.md >> %LOG% 2>&1
%PY% analysis\weekend_report.py --store store_%1 --data data_in\%1 --out reports\%1.md >> %LOG% 2>&1
echo [%1] done
exit /b

:answers
echo [%1] answers: collect from 3 models on all approved items (v3)
echo ==== [%1] answers >> %LOG%
%PY% collect_answers.py --store store_%1 --max-tokens 32000 >> %LOG% 2>&1
echo [%1] answers: retry failed calls (if any)
%PY% collect_answers.py --store store_%1 --max-tokens 32000 >> %LOG% 2>&1
%PY% run.py --store store_%1 ingest answers answers\store_%1\answers.jsonl --label "answers v3 all" >> %LOG% 2>&1
echo [%1] answers: grading
%PY% run.py --store store_%1 run --stage answer --workers 4 >> %LOG% 2>&1
%PY% run.py --store store_%1 run --stage answer --workers 4 >> %LOG% 2>&1
%PY% run.py --store store_%1 decide --stage answer >> %LOG% 2>&1
%PY% analysis\answer_report.py --store store_%1 --out reports\answers_%1.md >> %LOG% 2>&1
%PY% analysis\answer_table.py --store store_%1 >> %LOG% 2>&1
echo [%1] answers done
exit /b

:end
echo ==== %date% %time% end >> %LOG%
echo Finished. Log: %LOG%
endlocal
