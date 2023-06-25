import csv
import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import UniqueConstraint

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///survey.db'
db = SQLAlchemy(app)


class Response(db.Model):
    id = db.Column(db.String, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    q_index = db.Column(db.Integer, nullable=False)
    question = db.Column(db.String, nullable=False)
    response = db.Column(db.String, nullable=False)    
    
    __table_args__ = (UniqueConstraint('id', 'start_time', 'q_index', name='uix_1'), )

db.create_all()


## TODO: add a will not answer button to the range input

class Question:
    def __init__(self, q_type, prompt, options=None, mandatory=False):
        self.type = q_type
        self.prompt = prompt
        self.options = options
        self.mandatory = mandatory

## TODO: Consider adding a new page to create and add questions
questions = [
    Question('text', 'What is your name?', mandatory=True),
    Question('text', 'What is your favorite color?'),
    Question('choice', 'What is your favorite pet?', ['Dog', 'Cat', 'Bird', 'Other']),
    Question('choice', 'What is your favorite fruit?', ['Apple', 'Banana', 'Cherry', 'Other']),
    Question('range', 'On a scale of 1 to 10, how do you feel today?', mandatory=True),
    Question('range', 'On a scale of 1 to 10, how much do you like ice cream?', mandatory=True),
]

@app.route('/', methods=['GET', 'POST'])
def start():
    # clear the session
    session.clear()
    session['responses'] = {}
    session['sid'] = str(uuid.uuid4())
    session['start_time'] = datetime.utcnow()
    session['q_index'] = 0
    
    ## TODO: remove POST after checking- this is possibly never accessed
    if request.method == 'POST':
        return jsonify(success=True)
    else:
        return redirect(url_for('question'))

@app.route('/reset', methods=['POST'])
def reset():
    # Reset the session and start new survey
    session.clear()
    session['responses'] = {}
    session['sid'] = str(uuid.uuid4())
    session['start_time'] = datetime.utcnow()
    session['q_index'] = 0
    return '', 204  # Return 204, indicating that the request has succeeded but there's no representation to return (i.e. no body)

@app.route('/question', methods=['GET', 'POST'])
def question():
    # if session doesn't have an sid, start a new session
    if 'sid' not in session:
        return redirect(url_for('start'))

    q_index = session.get('q_index', 0)
    current_answer = session['responses'].get(questions[q_index].prompt, '')

    error=None
    
    if request.method == 'POST':
        action = request.form.get('action')
        answer = request.form.get('response', '').strip()
        question = "Question {}".format(q_index + 1)

        # handle missing or bad inputs
        if questions[q_index].mandatory and answer == '':
            error = 'This is a required question. Please enter a response before you can move on.'
        else:
            # save response
            session['responses'][questions[q_index].prompt] = answer if answer else None
        
            response = answer
            
            ## Write to db
            # Check if a response already exists for the current session and question index
            response = Response.query.filter_by(id=session['sid'], q_index=q_index).first()
            
            if response:
                # If a response exists, update it
                response.response = response_text
            else:
                # If a response doesn't exist, create a new one
                response = Response(id=session['sid'], start_time=session['start_time'], q_index=q_index,
                                question=question, response=response_text)
                db.session.add(response)

            db.session.commit()

            # redirect to next question or previous question based on action
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

    return render_template('question.html', question=questions[q_index], error=error, current_answer=current_answer)


@app.route('/done')
def done():
    return 'Thank you for your responses!'

@app.route('/results', methods=['GET'])
def results():
    responses = Response.query.order_by(Response.start_time, Response.id, Response.q_index).all()
    return render_template('results.html', responses=responses)

if __name__ == '__main__':
    app.run(debug=True)
