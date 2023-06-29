import os
import sys
import csv
import io
import argparse
import gcsfs
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, \
    session, jsonify, g

from google.cloud import storage
from http import HTTPStatus
import uuid

#############################################################
## Initializations
#############################################################

app = Flask(__name__)
app.config['SECRET_KEY'] = 'auth_not_supported_dummy_secret_key'

CSV_FILE_NAME = 'survey_responses.csv'
CSV_COLUMN_NAMES = ['session_id', 'start_time', 'q_index', 'question',
                    'response']
PROJECT_ID = 'inbuild-dee'
BUCKET_NAME = 'inbuild-dee.appspot.com'

def create_csv():
    # create a client
    storage_client = storage.Client(PROJECT_ID)

    # get the bucket
    bucket = storage_client.get_bucket(BUCKET_NAME)

    # create a new blob (i.e. a new file in GCP terms)
    blob = bucket.blob(CSV_FILE_NAME)

    # Check if the blob already exists
    if not blob.exists():
        # initialize csv data
        csv_data = ','.join(CSV_COLUMN_NAMES) + '\n'
        blob.upload_from_string(csv_data)

    print(f"CSV file {CSV_FILE_NAME} created in GCS bucket {BUCKET_NAME}.")

create_csv()

class Question:

    def __init__(
        self,
        q_type,
        prompt,
        options=None,
        mandatory=False,
        range_min=None,
        range_max=None,
        range_min_label=None,
        range_max_label=None,
        ):

        self.type = q_type
        self.prompt = prompt
        self.options = options
        self.mandatory = mandatory
        self.range_min = range_min
        self.range_max = range_max
        self.range_min_label = range_min_label
        self.range_max_label = range_max_label


questions = [
    Question('text', 'What is your name?', mandatory=True),
    Question('text', 'What is your favorite color?'),
    Question('choice', 'What is your favorite pet?', ['Dog', 'Cat',
             'Bird', 'Other']),
    Question('choice', 'What is your favorite fruit?', ['Apple',
             'Banana', 'Cherry', 'Other']),
    Question(
        'range',
        'On a scale of 1 to 6, how do you feel today?',
        mandatory=True,
        range_min=1,
        range_max=6,
        range_min_label='Sad',
        range_max_label='Happy',
        ),
    Question(
        'range',
        'On a scale of 1 to 6, how much do you like ice cream?',
        mandatory=True,
        range_min=1,
        range_max=6,
        range_min_label='Not at all',
        range_max_label='Quite a bit',
        ),
    ]


#############################################################
## Storage interface
#############################################################

def write_response_csv(response):
    try:

        # Load existing data

        data = []
        
        # create a client
        storage_client = storage.Client(PROJECT_ID)

        # get the bucket
        bucket = storage_client.get_bucket(BUCKET_NAME)

        # Get the blob
        blob = bucket.blob(CSV_FILE_NAME)
        
        if blob.exists():
            # Load the data from GCP bucket into a DictReader
            csv_file = blob.download_as_text().splitlines()
            data = list(csv.DictReader(csv_file))

        # Check if response already exists and update it

        existing_response = next((item for item in data
                                 if item['session_id']
                                 == response['session_id']
                                 and item['q_index']
                                 == str(response['q_index'])), None)
        if existing_response:
            existing_response['response'] = response['response']
        else:
            data.append(response)

        # Write data back to GCS bucket
        csv_data = io.StringIO()
        writer = csv.DictWriter(csv_data, fieldnames=CSV_COLUMN_NAMES)
        writer.writeheader()
        writer.writerows(data)
        blob.upload_from_string(csv_data.getvalue())
        
    except csv.Error as e:
        return f'Error processing CSV file: {e}'


def results_csv():
    try:
        gcp_path = f"gs://{BUCKET_NAME}/{CSV_FILE_NAME}"

        client = storage.Client()
        bucket = client.get_bucket(BUCKET_NAME)

        blob = storage.Blob(CSV_FILE_NAME, bucket)
        content = blob.download_as_text()

        reader = csv.DictReader(content.splitlines())
        
        responses = [dict(row) for row in reader]
        responses.sort(key=lambda r: (r['start_time'], r['session_id'], int(r['q_index'])))
        
        return render_template('results.html', responses=responses)
    except FileNotFoundError:
        return 'No responses available.'


## Storage interface
#############################################################

#############################################################
## Flask App functions
#############################################################

@app.route('/', methods=['GET', 'POST'])
def start():
    reset_session()
    return redirect(url_for('question', q_index=0))


@app.route('/results', methods=['GET'])
def results():
    return results_csv()


@app.route('/reset', methods=['POST'])
def reset():

    # Reset the session and start new survey

    reset_session()
    return ('', HTTPStatus.NO_CONTENT)  # success, but empty response


@app.route('/question', methods=['GET', 'POST'])
def question():
    if 'sid' not in session:
        return redirect(url_for('start'))
    q_index = session.get('q_index', 0)
    error = None
    current_answer = session['responses'
                             ].get(questions[q_index].prompt, '')
    question = questions[q_index]

    if request.method == 'POST':
        answer = request.form.get('response', '').strip()
        action = request.form.get('action')
        
        ## Note, writing all inputs, even empty ones to indicate that
        ## this is a question the user has seen but is choosing not to answer.
        ## This does not apply to Mandatory questions which will never have empty answers.
        if action == 'Next':

            # Valid inputs, can move forward

            if not question.mandatory or question.mandatory and answer \
                != '':
                response = parse_and_set_answer(question, q_index,
                        answer)
                write_response(response)
                return navigate(action, q_index)
            else:
                error = \
                    'This is a required question. Please enter a response before you can move on.'

                # clear past responses if any

                session['responses'][question.prompt] = None
        elif action == 'Back':
            response = parse_and_set_answer(question, q_index, answer)

            # don't save mandatory unanswered questions. We are saving non-mandatory
            # blanks to allow the db reader to see these questions were "viewed"
            # by the user, but deliberately not answered.

            if not question.mandatory or question.mandatory and answer \
                != '':
                write_response(response)
            return navigate(action, q_index)

        # Fall-through, update current answer in case it changed.

        current_answer = session['responses'][question.prompt]

    # Fall-through to GET or insisting user answers a question before moving forward.
    return render_template('question.html', question=question,
                           error=error, current_answer=current_answer,
                           show_back_button=q_index > 0)


@app.route('/done')
def done():
    reset_session()
    return 'Thank you for your responses!'

#############################################################

#############################################################
## Utils
#############################################################

def reset_session():
    session.clear()
    session['responses'] = {}
    session['sid'] = str(uuid.uuid4())
    session['start_time'] = datetime.utcnow()
    session['q_index'] = 0


def write_response(response):
    return write_response_csv(response)


def parse_and_set_answer(question, q_index, answer):
    if question.type == 'range':
        session['responses'][question.prompt] = \
            (int(answer) if answer else None)
    else:
        session['responses'][question.prompt] = \
            (answer if answer else '')

    response = {
        'session_id': session['sid'],
        'start_time': session['start_time'],
        'q_index': q_index,
        'question': question.prompt,
        'response': session['responses'][question.prompt],
        }
    return response


def navigate(action, q_index):
    if action == 'Next':
        if q_index < len(questions) - 1:
            session['q_index'] += 1
            return redirect(url_for('question'))
        else:
            return redirect(url_for('done'))
    elif action == 'Back':

        # note: we strictly don't need to check for q_index > 0 for Back button clicks
        # because we disabled the Back button for the first input. But are doing so to
        # decouple client-server checks

        if q_index > 0:
            session['q_index'] -= 1
            return redirect(url_for('question'))
    return None


## Utils
#############################################################

if __name__ == '__main__':
    app.run(debug=True)
