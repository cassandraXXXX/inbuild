import csv, os, uuid
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime

CSV_FILE_NAME = 'survey_responses.csv'
CSV_COLUMN_NAMES = ['session_id', 'start_time', 'q_index', 'question', 'response']
DEFAULT_RANGE_SLIDER = 5

app = Flask(__name__)

## add a will not answer button to the range input

class Question:
    def __init__(self, q_type, prompt, options=None, mandatory=False):
        self.type = q_type
        self.prompt = prompt
        self.options = options
        self.mandatory = mandatory

questions = [
    Question('text', 'What is your name?', mandatory=True),
    Question('text', 'What is your favorite color?'),
    Question('choice', 'What is your favorite pet?', ['Dog', 'Cat', 'Bird', 'Other']),
    Question('choice', 'What is your favorite fruit?', ['Apple', 'Banana', 'Cherry', 'Other']),
    Question('range', 'On a scale of 1 to 10, how do you feel today?', mandatory=True),
    Question('range', 'On a scale of 1 to 10, how much do you like ice cream?', mandatory=True),
]

def reset_session():
    session.clear()
    session['responses'] = {}
    session['sid'] = str(uuid.uuid4())
    session['start_time'] = datetime.utcnow()
    session['q_index'] = 0

@app.route('/', methods=['GET', 'POST'])
def start():
    # Check and write headers if the file is new
    if not os.path.isfile(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMN_NAMES)

    reset_session()
    
    ## TODO: remove POST after checking- this is possibly never accessed
    return redirect(url_for('question')) if request.method == 'GET' else jsonify(success=True)

@app.route('/reset', methods=['POST'])
def reset():
    # Reset the session and start new survey
    reset_session()
    return '', 204  # Return 204, indicating that the request has succeeded but there's no representation to return (i.e. no body)

def write_response(response):
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

@app.route('/question', methods=['GET', 'POST'])
def question():
    # if session doesn't have an sid, start a new session
    if 'sid' not in session:
        return redirect(url_for('start'))
    q_index = session.get('q_index', 0)
    error=None
    current_answer = session['responses'].get(questions[q_index].prompt, '')
    current_answer = DEFAULT_RANGE_SLIDER if current_answer == '' and 
        questions[q_index].type == "range" else current_answer
    
    if request.method == 'POST':
        answer = request.form.get('response', '').strip()
        question = "Question {}".format(q_index + 1)

        # handle missing or bad inputs
        if questions[q_index].mandatory and answer == '':
            error = 'This is a required question. Please enter a response before you can move on.'
        else:
            # save response
            session['responses'][questions[q_index].prompt] = answer if answer else None
            
            response = {
                'session_id': session['sid'],
                'start_time': session['start_time'],
                'q_index': q_index,
                'question': question,
                # todo check for nulls in DB
                'response': session['responses'][questions[q_index].prompt]
            }
        
            write_response(response)
               
            # redirect to next question or previous question based on action
            session['q_index'] += 1 if request.form.get('action') == 'Next' else -1
            
            # redirect to next question or previous question based on action
            action = request.form.get('action')
            if action == 'Next':
                if q_index < len(questions) - 1:
                    session['q_index'] += 1
                    return redirect(url_for('question'))
                else:
                    return redirect(url_for('done'))
            elif action == 'Back':
                if q_index > 0:
                    session['q_index'] -= 1
                    return redirect(url_for('question'))

    ## Fallback to 'GET' or missing input for a mandatory question
    return render_template('question.html', question=questions[q_index], error=error, current_answer=current_answer)


@app.route('/done')
def done():
    return 'Thank you for your responses!'

@app.route('/results', methods=['GET'])
def results():
    responses = []
    with open(CSV_FILE_NAME, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            responses.append(dict(zip(headers, row)))
    responses.sort(key=lambda r: (r['start_time'], r['session_id'], int(r['q_index'])))
    return render_template('results.html', responses=responses)

if __name__ == '__main__':
    app.run(debug=True)
