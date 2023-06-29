# Goals
Build a survey app similar to Typeform, in python. Enable access to results of past Surveys through a separate endpoint.
- [Original Prompt](https://docs.google.com/document/d/1yrWI6qZMJdweb4mnaftItBG-8ChmB4NIU5RsjIo-M_U/edit)
- Code should make it easy to add questions
- Nav: Hitting browser refresh will restart the user session and survey. Back and Next will help the user navigate through the survey
- Results: Store in-progress and submitted responses

# Versions
There are two directories `survey-app` and `survey-app-gcp`. The first is for optimized for local runs. It uses the local
file system to store data. And has the option to use csvs and SQLite for efficiency. 
This version will also work with GCP, but will store data to a /tmp folder that's fairly ephemeral. This is because AppEngine
doesn't support writes due to its distributed nature.

The second, `survey-app-gcp`, works with GCP's persistent cloud storage buckets. In addition to the results end-point, you 
can find data for this [here](https://ff60761d5b5c51af3339904f293779e161c38f868d1663bc9266b90-apidata.googleusercontent.com/download/storage/v1/b/inbuild-dee.appspot.com/o/survey_responses.csv?jk=AYvHSRFW9sADhchChugy0eXVXK_ffP5ygErIJ6mUwbTz7cOWu1kcfJW5fkl7w0auPStBG0aO-wv9RcyXjdzG27hC7YO9h5O05SvjwzeaICLn4BDJQrH05Xc1pmEG2Upu4KiAPr50Sf4pMURqStwzOx8T_b7ECN4NxhcFA-Iew5z2qNBBFifrQS6ST4yVOY4NA9BfPZn-EkfNpnzvTXMqdcDlelt2NB7rFoKb0aI5LX3ffuyvCYTM_0JRQVTcwfWeBuzV5tgPqlAhjbEfJ13GYkFKS37Zmudnp5daQdWRzQsWDrM-IB0DS30lYQ1d_WqO6XARNCaa7NDXKXEfYSkZwonpz4kc4yTZ66VWIntDi-faBWHCcJS1IXQHINjFWkTlKA03YSYh7x6mRkBkAssZ_Wvj2wUVdgpkVmGGX2gO9i5tsbvJKsxt-1G92RtEJNhD_hP84kRTBaIa1RvqGyAMu6xGbRMu8_VJ54IIyT9ybsvwKRFR6YUtv618IMHU0RtT3EwI0529bEQTdD-e6JU6B7_bAvMf5S9wxJ38spDrdsWUwwHUd_wC4H--x9vH57D27fHkxANRME4gsYrTXQ2L-P9WX1sFrd7Mu3tW-KKJeGDHWT_Gb4zY-J_pf4NvLw7I4ibXC5ZdYlBNfaRgBvTvlZNcL7qFlA8nDtfA8fEkt3zXElmEReZQE4TIjYQE77MAemHx9oD0J32cP1YiWYGg7wXOHcR7BwEoXJT-XIIvJp5cP-FLPtFlZduFJLnplgk44nBsoyhi7CWigGzYTL-Gm0q1hnRF-4zH5syON0K2NLdDbcHsUJWee4sJ5NxSmzri9gbuhej45cYZDNNtIql4ifdsuSkU_vLJIwveXWNGvoEys6d38JrulkA1_WdSIt0kzohJikomI1EhnDryLspRawyORBujLdJQ2RGQCuPaCnJ7qTlIRDU_0QwWmRX8-l95GmrdO32ZbLDKCTSwsM_9G9ZxIujgESv4A_nOVelHNBRRYZg0O2CVoKV8RB1dCEOD5MUpimUttxLTJdckbNr8xXvYfN46Y3gheaikYbXZNR8ST1CEIXbJUxZRICIusTVL8BQDxOXxXOoX56GG_JXAgDpjwhMsOlkfrilZxZZ4U2oj3-KnIn422pk7jzUziaNS9H8vdvCRMqRe0rM78iVnizhblIDB49LYSbZFkT6gQzRD25VtPw&isca=1) .

Note, a csv on the bucket is not the most optimal pattern for large datasets, but works okay for this application. 
The next step would be to use a relational database on GCP.

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

