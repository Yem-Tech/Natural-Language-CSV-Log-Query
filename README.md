# Natural Language CSV Log Query

Ask common security questions about a CSV file. The OpenAI API translates the question into a restricted JSON plan; Python applies that plan locally. Log rows and API keys are not sent in the prompt. The tool streams the CSV, but grouping keeps one counter per distinct group and displayed matches are limited.

## Goal and design

The goal is to let a security analyst ask plain-language questions instead of writing filters by hand. The flow is: **question → OpenAI JSON query plan → plan validation → streaming CSV search → count, table, or grouped result**. The model receives only the question and CSV column names. It cannot run Python or SQL; local code checks the requested columns and operators before reading events. `app.py` provides the web interface, while `log_query.py` contains the query engine and command-line entry point.

## Setup

Requires Python 3.10+ and an OpenAI API key with billing enabled.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='your-key'
streamlit run app.py
```

The web page opens at `http://localhost:8501`. On a remote Ubuntu VM, forward port 8501 over SSH, or use an existing trusted port forwarding rule. Enter the API key in the sidebar if you did not set the environment variable; the field is masked. Upload a CSV, or choose the included sample, type a question and press **Run query**.

For the Ubuntu VM used in this demonstration, PuTTY connects to `127.0.0.1:2222` from Windows. In a separate Windows PowerShell window, the following SSH tunnel makes the web app available at `http://localhost:8501` while both terminals remain open:

```powershell
ssh -N -L 8501:127.0.0.1:8501 -p 2222 admin@127.0.0.1
```

The command-line interface is also available:

```bash
python log_query.py sample_logs.csv 'Who logged in after working hours yesterday?' --timezone America/Halifax
```

On Windows PowerShell: `.venv\Scripts\Activate.ps1` and `$env:OPENAI_API_KEY='your-key'`. Never commit your key. For reproducible demonstrations with the included historical sample, ask for all logins after 5 PM rather than *yesterday*.

More questions: `Show all user activity`; `Show severe errors`; `Count failed login attempts yesterday`; `Count activity by user_name`. Questions depend on the real CSV headers and values. Output includes the interpreted plan and exact matching event count, plus up to 100 rows for search questions. `--limit 20` changes display size; `--timezone` controls relative dates and local hour comparisons. ISO 8601 timestamps with offsets are converted to that zone; timestamps without an offset are assumed already local to that zone.

The included data is synthetic. Review the plan shown with the result: exact wording in logs varies, so a model may choose an imperfect value such as `login` versus `logged in`. The current plan supports AND-combined case-insensitive text comparisons, today/yesterday, an after-time condition, counts, and one-column grouping. It does not handle OR, numeric ranges, arbitrary date ranges, joins, or deduplication. A group result counts events, not distinct users. Empty matches are reported as zero. CSV rows never execute as code.

## Demonstrated results

Tested on 2026-09-23 with the included six-event synthetic CSV and a live API request:

| Question | Result | Evidence |
| --- | --- | --- |
| Show me users who accessed the courses section | 3 events: Olatunji twice, Dennis once | `screenshots/07-web-app-courses-query.png` |
| Who logged in after working hours yesterday? | 2 successful events: Samuel and Mutwiri; the failed login was excluded | `screenshots/04-ai-after-hours-logins.png` |
| How many failed login attempts are in the logs? | 1 event from an uploaded CSV | `screenshots/08-web-app-uploaded-csv-count.png` |
| Count log events by user_name | 6 events grouped by user; Olatunji has 2 | `screenshots/06-ai-events-by-user.png` |

Relative dates depend on the run date and selected timezone. The sample was built around 2026-09-22 and 2026-09-23; after those dates, ask about a specific action without “yesterday” or update the sample timestamps to demonstrate relative dates again.

For sensitive production logs, assess whether sending header names and the user's question to the API is permitted. Restrict file access and output as appropriate; the result can contain personal data. Large-file performance is linear in the number of rows, so indexed storage is preferable for repeated searches at scale.
