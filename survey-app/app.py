import os
import sys
import csv
import sqlite3
import argparse
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from http import HTTPStatus
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'auth_not_supported_dummy_secret_key'

CSV_FILE_NAME = 'survey_responses.csv'
CSV_COLUMN_NAMES = ['session_id', 'start_time', 'q_index', 'question', 'response']
DATABASE = './responses.db'

class Question:
    def __init__(self, q_type, prompt, options=None, mandatory=False, 
                     range_min=None, range_max=None, range_min_label=None, range_max_label=None):
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
    Question('choice', 'What is your favorite pet?', ['Dog', 'Cat', 'Bird', 'Other']),
    Question('choice', 'What is your favorite fruit?', ['Apple', 'Banana', 'Cherry', 'Other']),
    Question('range', 'On a scale of 1 to 6, how do you feel today?', mandatory=True, range_min=1, range_max=6, range_min_label='Sad', range_max_label='Happy'),
    Question('range', 'On a scale of 1 to 6, how much do you like ice cream?', mandatory=True, range_min=1, range_max=6, range_min_label='Not at all', range_max_label='Quite a bit')
]

############################################################
## Storage interface

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def write_response_csv(response):
    try: 
        # Load existing data
        data = []
        if os.path.isfile(CSV_FILE_NAME):
            with open(CSV_FILE_NAME, 'r') as f:
                data = list(csv.DictReader(f))
            
        # Check if response already exists and update it
        existing_response = next((item for item in data 
                              if item['session_id'] == response['session_id'] 
                                  and item['q_index'] == str(response['q_index'])), None)
        if existing_response:
            existing_response['response'] = response['response']
        else:
            data.append(response)
        
        # Write data back to file
        with open(CSV_FILE_NAME, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMN_NAMES)
            writer.writeheader()
            writer.writerows(data)
            
    except csv.Error as e:
        return 'Error processing CSV file: {}'.format(e)

def write_response_db(response):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO responses VALUES (?, ?, ?, ?, ?)',
                   (response['session_id'], response['start_time'], 
                    response['q_index'], response['question'], response['response']))
    conn.commit()

def start_csv():
    return redirect(url_for('question', q_index=0))

def start_db():
    # Initialize the database and table if they don't exist
    conn = get_db()
    conn.execute('CREATE TABLE IF NOT EXISTS responses (session_id TEXT, start_time TEXT, q_index INTEGER, question TEXT, response TEXT, PRIMARY KEY (session_id, q_index))')
    conn.commit()
    return redirect(url_for('question', q_index=0))

def results_csv():
    responses = []
    if os.path.isfile(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'r') as f:
            if os.stat(CSV_FILE_NAME).st_size == 0:
                return "No responses available."
            else:
                reader = csv.reader(f)
                headers = next(reader)
                for row in reader:
                    responses.append(dict(zip(headers, row)))
        responses.sort(key=lambda r: (r['start_time'], r['session_id'], int(r['q_index'])))
        return render_template('results.html', responses=responses)
    else:
        return "No responses available."
    
def results_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM responses ORDER BY start_time, session_id, q_index")
    responses = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    if len(responses) == 0:
        return "No responses available."
    return render_template('results.html', responses=responses)

## Storage interface
############################################################

#############################################################
## Flask App functions
    
@app.route('/', methods=['GET', 'POST'])
def start():
    reset_session()
    if args.storage == 'csv':
        return start_csv()
    else:
        return start_db()

@app.route('/results', methods=['GET'])
def results():
    if args.storage == 'csv':
        return results_csv()
    else:
        return results_db()

@app.route('/reset', methods=['POST'])
def reset():
    # Reset the session and start new survey
    reset_session()
    return '', HTTPStatus.NO_CONTENT # success, but empty response

    
## Note, writing all inputs, even empty ones to indicate this is a question the user has seen
## but is choosing not to answer
@app.route('/question', methods=['GET', 'POST'])
def question():
    if 'sid' not in session:
        return redirect(url_for('start'))
    q_index = session.get('q_index', 0)
    error=None
    current_answer = session['responses'].get(questions[q_index].prompt, '')
    question = questions[q_index]

    if request.method == 'POST':
        answer = request.form.get('response', '').strip()
        action = request.form.get('action')
        
        if action == 'Next':
            # Valid inputs, can move forward
            if not question.mandatory or (question.mandatory and answer != ''):
                response = parse_and_set_answer(question, q_index, answer)
                write_response(response)
                return navigate(action, q_index)
            else: 
                error = 'This is a required question. Please enter a response before you can move on.'
                # clear past responses if any
                session['responses'][question.prompt] = None
        elif action == 'Back':
            response = parse_and_set_answer(question, q_index, answer)
            # don't save mandatory unanswered questions. We are saving non-mandatory
            # blanks to allow the db reader to see these questions were "viewed"
            # by the user, but deliberately not answered.
            if not question.mandatory or (question.mandatory and answer != ''):
                write_response(response)
            return navigate(action, q_index)
            
        # Fall-through, update current answer in case it changed.
        current_answer = session['responses'][question.prompt]

    return render_template('question.html', question=question, 
                           error=error, current_answer=current_answer, 
                           show_back_button=(q_index > 0))

@app.route('/done')
def done():
    reset_session()
    return 'Thank you for your responses!'

## Flask App
#############################################################

##########################################
## Utils

def reset_session():
    session.clear()
    session['responses'] = {}
    session['sid'] = str(uuid.uuid4())
    session['start_time'] = datetime.utcnow()
    session['q_index'] = 0
    
def write_response(response):
    if args.storage == 'csv':
        return write_response_csv(response)
    else:
        return write_response_db(response)
    
def parse_and_set_answer(question, q_index, answer):
    if question.type == 'range':
        session['responses'][question.prompt] = int(answer) if answer else None
    else:
        session['responses'][question.prompt] = answer if answer else ''

    response = {
        'session_id': session['sid'],
        'start_time': session['start_time'],
        'q_index': q_index,
        'question': question.prompt,
        'response': session['responses'][question.prompt]
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
##########################################

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage', choices=['csv', 'db'], default='csv')
    args = parser.parse_args()
    app.run(debug=True)
