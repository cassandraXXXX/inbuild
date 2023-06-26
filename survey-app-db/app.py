import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from datetime import datetime
import uuid

DATABASE = './responses.db'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Using SQLLite to make installation and running easier
# For higher efficiency and volume, use SQLAlchemy that has
# connection pooling etc. baked in

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

def reset_session():
    session.clear()
    session['responses'] = {}
    session['sid'] = str(uuid.uuid4())
    session['start_time'] = datetime.utcnow()
    session['q_index'] = 0

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

def write_response(response):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO responses (session_id, start_time, q_index, question, response) VALUES (?, ?, ?, ?, ?) \
        ON CONFLICT(session_id, q_index) DO UPDATE SET response = excluded.response",
        (response['session_id'], response['start_time'], response['q_index'], response['question'], response['response'])
    )
    conn.commit()

@app.route('/', methods=['GET', 'POST'])
def start():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                session_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                q_index INTEGER NOT NULL,
                question TEXT NOT NULL,
                response TEXT,
                PRIMARY KEY(session_id, q_index)
            )
        """)
        db.commit()

    reset_session()

    return redirect(url_for('question')) if request.method == 'GET' else jsonify(success=True)

@app.route('/reset', methods=['POST'])
def reset():
    reset_session()
    return '', 204

## Note, writing all inputs, even empty ones to indicate this is a question the user has seen
## but is choosing not to answer
@app.route('/question', methods=['GET', 'POST'])
def question():
    if 'sid' not in session:
        return redirect(url_for('start'))
    q_index = session.get('q_index', 0)
    error=None
    current_answer = session['responses'].get(questions[q_index].prompt, '')

    if request.method == 'POST':
        answer = request.form.get('response', '').strip()
        question = questions[q_index].prompt
        action = request.form.get('action')

        if questions[q_index].mandatory and answer == '' and action != 'Back':
            error = 'This is a required question. Please enter a response before you can move on.'
        elif questions[q_index].mandatory and answer == '' and action == 'Back':
            if q_index > 0:
                    session['q_index'] -= 1
                    return redirect(url_for('question'))
        else:
            if questions[q_index].type == 'range':
                session['responses'][questions[q_index].prompt] = int(answer) if answer else None
            else:
                session['responses'][questions[q_index].prompt] = answer if answer else ''

            response = {
                'session_id': session['sid'],
                'start_time': session['start_time'],
                'q_index': q_index,
                'question': question,
                'response': session['responses'][questions[q_index].prompt]
            }
        
            write_response(response)

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

    return render_template('question.html', question=questions[q_index], 
                           error=error, current_answer=current_answer, 
                           show_back_button=(q_index > 0))

@app.route('/done')
def done():
    return 'Thank you for your responses!'

@app.route('/results', methods=['GET'])
def results():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM responses ORDER BY start_time, session_id, q_index")
    responses = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
    if len(responses) == 0:
        return "No responses available."
    return render_template('results.html', responses=responses)

if __name__ == '__main__':
    app.run(debug=True)
