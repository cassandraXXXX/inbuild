# Goals
Build a survey app similar to Typeform, in python. Enable access to results of past Surveys through a separate endpoint.
- [Original Prompt](https://docs.google.com/document/d/1yrWI6qZMJdweb4mnaftItBG-8ChmB4NIU5RsjIo-M_U/edit)
- Code should make it easy to add questions
- Nav: Hitting browser refresh will restart the user session and survey. Back and Next will help the user navigate through the survey
- Results: Store in-progress and submitted responses

# Access and Run

## Local running
`python3 app.py`

The above defaults to using CSV for storage. You can configure to use csv or db using command-line args

`python3 app.py  --storage=[db|csv]`

## Local Access
The above command will deploy locally. You can access both survey and results on localhost

Survey: http://127.0.0.1:5000/question

Results: http://127.0.0.1:5000/results

## GCP Configuration

You can configure the GCP instance through the `app.yaml` file. Currently, only the storage variable is set to db by default. 
You can change it to csv if you'd like to use a readable file. 
`env_variables:
  STORAGE: "db"`

## GCP Access

Survey: https://inbuild-dee.wn.r.appspot.com/

Results: https://inbuild-dee.wn.r.appspot.com/results

# Functionality and Design choices

## Storage
- Supports both csv and a SqlLite db. Purely for legacy and debugging reasons. Csv was the first format I implemented because it was easy to read and debug with. Csv’s not efficient so SqlLite is the better choice in general
- Scaling - if you need to scale you’ll want to use SQLAlchemy and use a Postgres etc. instance. SQLLite works well for smaller datasets as is the case for us

## Results & Navigation
- **Format** - Results are formatted as one line per user_session, start_time and question. I’m using start_time to group and display results so it’s easier to read. The session id is a unique identifier that’s reset on refreshes, and resets with new sessions
- **Sessions** - Sessions restart on hitting browser refresh. This means a new session_id and a session_start time. Hitting Next and back sustain and keep the session id asis.
- **Updates** - results are update every time a new answer is entered and an existing answer is changed. If a mandatory question is not answered and the person moves back, the answer is not recorded. This is not true for non-mandatory questions where empty responses are recorded to indicate the user has viewed the question.

## Etc. 
- Tested for parallel connections on GCP and it works
- Questions are easily editable in the questions variable initialization at the top
- Supports three types of questions - text input, multiple choice and range. Range questions have range values, min and max, and min and max labels configurable
- Running on GCP versus locally requires to be passed in differently. GCP uses the “STORAGE” env variable. Local runs can use that, but also also use command line arguments. 

# Improvements

- Cloud storage - GCP’s app engine forces me to store all data in a temp directory as write operations are not permitted. This isn’t desirable because the data is relatively ephemeral. Future improvements will use either GCP’s distributed storage to store the application’s db.
- Change the next button to Submit on the last question
- Clean and divide app.py into chunks to improve readability

