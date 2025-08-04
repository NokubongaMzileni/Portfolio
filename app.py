import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, g, jsonify
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import os
from dotenv import load_dotenv


load_dotenv()

session_cleared = False



app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

@app.before_request
def clear_session_on_first_request():
    global session_cleared
    if not session_cleared:
        session.clear()
        session_cleared = True


DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, timeout=10)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    with sqlite3.connect(DATABASE, timeout=10) as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                movieId INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                genres TEXT
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userId INTEGER,
                movieId INTEGER,
                rating REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(userId) REFERENCES users(id),
                FOREIGN KEY(movieId) REFERENCES movies(movieId)
            )
        ''')
        db.commit()


def load_csv_data():
    with sqlite3.connect(DATABASE, timeout=10) as db:
        
        movies_path = os.path.join('data', 'movies.csv')
        if os.path.exists(movies_path):
            movies_df = pd.read_csv(movies_path)
            for _, row in movies_df.iterrows():
                try:
                    db.execute(
                        'INSERT OR IGNORE INTO movies (movieId, title, genres) VALUES (?, ?, ?)',
                        (int(row['movieId']), row['title'], row.get('genres', ''))
                    )
                except Exception as e:
                    print(f"Error inserting movie {row['title']}: {e}")

       
        ratings_path = os.path.join('data', 'ratings.csv')
        if os.path.exists(ratings_path):
            ratings_df = pd.read_csv(ratings_path)
            for _, row in ratings_df.iterrows():
                try:
                    db.execute(
                        'INSERT OR IGNORE INTO ratings (userId, movieId, rating, timestamp) VALUES (?, ?, ?, ?)',
                        (int(row['userId']), int(row['movieId']), float(row['rating']), row.get('timestamp', None))
                    )
                except Exception as e:
                    print(f"Error inserting rating for user {row['userId']} movie {row['movieId']}: {e}")

        db.commit()


@app.route('/')
def home():
    print("Home route accessed")
    if 'user_id' in session:
        return redirect(url_for('recommend'))
    return render_template('index.html',error=None)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            db = get_db()
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = "Username already exists!"
    return render_template('signup.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db('SELECT * FROM users WHERE username=? AND password=?', (username, password), one=True)
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('recommend'))
        else:
            error = "Invalid username or password!"
    return render_template('index.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

def get_user_ratings(user_id):
    ratings = query_db('SELECT movieId, rating FROM ratings WHERE userId=?', (user_id,))
    return {movieId: rating for (movieId, rating) in ratings}

def content_based_recommendations(user_ratings, top_n=5):
    db = get_db()
    movies_df = pd.read_sql_query("SELECT * FROM movies", db)

   
    if movies_df.empty:
        return []

    
    if not user_ratings:
        n = min(top_n, len(movies_df))
        return movies_df.sample(n)['title'].tolist()

   
    tfidf = TfidfVectorizer(token_pattern=r'[a-zA-Z0-9\-]+')
    tfidf_matrix = tfidf.fit_transform(movies_df['genres'].fillna(''))

  
    movie_id_to_idx = pd.Series(movies_df.index, index=movies_df['movieId']).to_dict()

   
    user_vec = np.zeros(tfidf_matrix.shape[1])
    for movieId, rating in user_ratings.items():
        idx = movie_id_to_idx.get(movieId)
        if idx is not None:
            user_vec += rating * tfidf_matrix[idx].toarray()[0]

   
    if np.linalg.norm(user_vec) == 0:
        n = min(top_n, len(movies_df))
        return movies_df.sample(n)['title'].tolist()

    sim_scores = cosine_similarity([user_vec], tfidf_matrix).flatten()
    sim_scores_idx = sim_scores.argsort()[::-1]

   
    recommended_titles = []
    for idx in sim_scores_idx:
        movieId = movies_df.iloc[idx]['movieId']
        if movieId not in user_ratings:
            recommended_titles.append(movies_df.iloc[idx]['title'])
        if len(recommended_titles) >= top_n:
            break

    return recommended_titles


@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    if 'user_id' not in session:
        return redirect(url_for('home'))

    user_id = session['user_id']
    recommendations = []
    search_results = []
    search_term = ''

    db = get_db()

    if request.method == 'POST':
       
        if 'movieId' in request.form and 'rating' in request.form:
            movieId = int(request.form['movieId'])
            rating = float(request.form['rating'])
            existing = query_db('SELECT * FROM ratings WHERE userId=? AND movieId=?', (user_id, movieId), one=True)
            if existing:
                db.execute('UPDATE ratings SET rating=? WHERE userId=? AND movieId=?', (rating, user_id, movieId))
            else:
                db.execute('INSERT INTO ratings (userId, movieId, rating) VALUES (?, ?, ?)', (user_id, movieId, rating))
            db.commit()
        
        
        if 'search' in request.form:
            search_term = request.form['search']
            like_pattern = f"%{search_term}%"
            search_results = query_db('SELECT movieId, title FROM movies WHERE title LIKE ? LIMIT 50', (like_pattern,))

    user_ratings = get_user_ratings(user_id)
    recommendations = content_based_recommendations(user_ratings)

    
    movies = query_db('SELECT movieId, title FROM movies LIMIT 50')

    return render_template('recommend.html',
                           username=session['username'],
                           recommendations=recommendations,
                           movies=movies,
                           search_results=search_results,
                           search_term=search_term)


 
    user_ratings = get_user_ratings(session['user_id'])
    recommendations = content_based_recommendations(user_ratings)

   
    db = get_db()
    movies = query_db('SELECT movieId, title FROM movies LIMIT 50')

    return render_template('recommend.html', username=session['username'], recommendations=recommendations, movies=movies)

if __name__ == '__main__':
    with app.app_context():
        init_db()
        load_csv_data()
        port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    app.run(debug=True)

