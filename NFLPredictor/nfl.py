# Uses a database of NFL Scores from 2002-2023 to visualize
# line graphs of a particular team's home or away scores,
# as well as a projection of their home or away scores for
# a particular time period

import datetime
import io
import os
import sqlite3 as sl

from datetime import date
import pandas as pd
from flask import Flask, redirect, render_template, request, session, url_for, send_file
from matplotlib.figure import Figure
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
db = "nfl.db"


@app.route("/")
def home():
    options = {
        "score_home": "Home Team",
        "score_away": "Away Team"
    }
    # Opens home page
    return render_template("nfl_home.html", teams=db_get_teams(), message="Please enter an NFL team to find scores for.",
                           options=options)


# Opens team-specific page
@app.route("/submit_team", methods=["POST"])
def submit_team():
    print(request.form['team'])
    session["team"] = request.form["team"]
    # Error handling for incorrect direct access of URLs
    if 'team' not in session or session["team"] == "":
        return redirect(url_for("home"))
    if "data_request" not in request.form:
        return redirect(url_for("home"))
    session["data_request"] = request.form["data_request"]
    print("Data request:")
    print(request.form['data_request'])
    return redirect(url_for("team_current", data_request=session["data_request"], team=session["team"]))


# Displays correct graph & page
@app.route("/api/nfl/<data_request>/<team>")
def team_current(data_request, team):
    # Shows the correct title for projected/not projected graphs
    project = False
    if 'date' in session and session['date'] != "":
        project = True
    return render_template("nfl.html", data_request=data_request, team=team, project=project)


# Calls page for team-specific projection
@app.route("/submit_projection", methods=["POST"])
def submit_projection():
    if 'team' not in session:
        return redirect(url_for("home"))
    session["date"] = request.form["date"]
    # Error handling intermediary for incorrect URLs
    if session["team"] == "" or session["data_request"] == "" or session["date"] == "":
        del session["date"]
        return redirect(url_for("home"))
    return redirect(url_for("team_projection", data_request=session["data_request"], team=session["team"]))


@app.route("/api/nfl/<data_request>/projection/<team>")
def team_projection(data_request, team):
    return render_template("nfl.html", data_request=data_request, team=team, project=True, date=session["date"])


# Displays the graphs themselves on the webpage
@app.route("/fig/<data_request>/<team>")
def fig(data_request, team):
    fig = create_figure(data_request, team)

    img = io.BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    return send_file(img, mimetype="image/png")

# Creates figure to be sent to the page
def create_figure(data_request, team):
    df = db_create_dataframe(data_request, team)
    print(session)
    # If a projection isn't to be made
    if 'date' not in session:
        fig = Figure()

        fig.suptitle(data_request.split('_')[1].capitalize() + " scores for the " + team)

        axes = df.plot('date', data_request, color='blue')
        axes.set_xlabel('Date')
        axes.set_ylabel('Points Scored')

        return axes.get_figure()
    else:
        # Reinstantiates db including all data for ML purposes
        conn = sl.connect(db)
        curs = conn.cursor()

        home_away = data_request.split('_')[1]

        query = 'SELECT * FROM nfl'

        df_sql_query = pd.read_sql_query(query, conn)
        df = pd.DataFrame(df_sql_query, columns=['date', data_request, home_away])
        print('back to df:\n', df.head(3))

        conn.close()

        # Defines the range of the data to be displayed
        range = session['date']
        bottom_range = range.split('-')[0] + '-01-01'
        top_range = range.split('-')[1] + '-12-31'
        print("bottom range", bottom_range)
        print("top range", top_range)
        d_bottom = date.fromisoformat(bottom_range)
        d_top = date.fromisoformat(top_range)

        bottom_ord = int(d_bottom.toordinal())
        top_ord = int(d_top.toordinal())

        # if bottom range is larger swap and continue
        if bottom_ord > top_ord:
            temp = bottom_ord
            bottom_ord = top_ord
            top_ord = temp

        print("bottom ord", bottom_ord)
        print("top ord", top_ord)

        # Change date to ordinal for ML
        df['DATE_ORD'] = pd.to_datetime(df['date']) \
            .map(datetime.datetime.toordinal).dropna()
        print(df.head(3))
        X_train, X_test, y_train, y_test = \
            train_test_split(df['DATE_ORD'], df[data_request],
                             test_size=0.99, random_state=0)
        model = KNeighborsClassifier(n_neighbors=2)

        model.fit(X_train.values.reshape(-1, 1), y_train)
        y_pred = model.predict(X_test.values.reshape(-1, 1))

        # Make a new dataframe to house and plot predictions
        df_pred = pd.DataFrame()
        df_pred['Predicted Score'] = y_pred
        df_pred['Observed Score Validation Set'] = y_test
        df_pred['X_test'] = X_test
        df_pred['DATE_ORD'] = df['DATE_ORD']
        df_pred[home_away] = df[home_away]
        print(df_pred.head(30))
        df_pred = df_pred.dropna()  # get rid of NaNs

        # Change 'date' back to normal formatting
        df_pred['date'] = df_pred['X_test'].astype(int) \
            .map(datetime.datetime.fromordinal)
        # Drop all rows not related to the home/away team indicated
        index_names = df_pred[df_pred[home_away] != team].index
        df_pred.drop(index_names, inplace=True)

        # Drop all rows outside of date range
        index_names = df_pred[df_pred['DATE_ORD'] < bottom_ord].index
        df_pred.drop(index_names, inplace=True)

        index_names = df_pred[df_pred['DATE_ORD'] > top_ord].index
        df_pred.drop(index_names, inplace=True)

        # Create figure to be returned
        fig = Figure()
        fig.suptitle("Predicted " + data_request.split('_')[1].capitalize() + " scores for the " + team)

        axes = df_pred.plot('date', 'Predicted Score', color='orange')
        axes.set_xlabel('Date')
        axes.set_ylabel('Points Scored')
        return axes.get_figure()

# Creates dataframe to be used for creating figures
def db_create_dataframe(data_request, team):
    conn = sl.connect(db)
    curs = conn.cursor()

    # Uses score_away/score_home (data_request) to determine
    # whether you should use the 'home' or 'away' column.
    home_away = data_request.split('_')[1]

    query = 'SELECT * FROM nfl'

    # Creates dataframe with columns 'date', 'score_home'/'score_away', 'home'/'away'
    df_sql_query = pd.read_sql_query(query, conn)
    df = pd.DataFrame(df_sql_query, columns=['date', data_request, home_away])
    print('back to df:\n', df.head(3))

    # Drop all rows not related to the home/away team indicated
    index_names = df[df[home_away] != team].index
    df.drop(index_names, inplace=True)
    print('df after drop:\n', df.head(30))

    conn.close()
    return df

# Returns the list of teams from the database
def db_get_teams():
    conn = sl.connect(db)
    curs = conn.cursor()

    table = "nfl"
    stmt = "SELECT `home` from " + table
    data = curs.execute(stmt)
    # sort a set comprehension for unique values
    teams = sorted({result[0] for result in data})
    conn.close()
    return teams


# Redirects all bad paths to home
@app.route('/<path:path>')
def catch_all(path):
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.secret_key = os.urandom(12)
    app.run(debug=True)
