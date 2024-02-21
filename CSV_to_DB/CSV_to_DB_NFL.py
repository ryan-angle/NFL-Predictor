import datetime
import io
import sqlite3 as sl

import pandas as pd
from matplotlib import pyplot as plt

pd.set_option('display.max_columns', None)

# Create/Connect database
conn = sl.connect('nfl.db')
curs = conn.cursor()

# Create our table if it doesn't already exist
# Manually specify table name, column names, and columns types
curs.execute('DROP TABLE IF EXISTS nfl')
curs.execute('CREATE TABLE IF NOT EXISTS '
             'nfl (`DATE` text, `HOME` text, `AWAY` text, `HOME_SCORE` number, `AWAY_SCORE` number)')
conn.commit()  # don't forget to commit changes before continuing

# Use pandas which you already to know to read the csv to df
# Select just the columns you want using optional use columns param
df = pd.read_csv('nfl_stats.csv', usecols=['date', 'away', 'home', 'score_away', 'score_home'])
print('First 3 df results:')
print(df.head(3))

# Let pandas do the heavy lifting of converting a df to a db
# name=your existing empty db table name, con=your db connection object
# just overwrite if the values already there, and don't index any columns
df.to_sql(name='nfl', con=conn, if_exists='replace', index=False)

# The rest is from the DB lecture and HW
print('\nFirst 3 db results:')
query = 'SELECT * FROM nfl'
results = curs.execute(query).fetchmany(3)
for result in results:
    print(result)

result = curs.execute('SELECT COUNT(*) FROM nfl').fetchone()
# Note indexing into the always returned tuple w/ [0]
# even if it's a tuple of one
print('\nNumber of valid db rows:', result[0])
print('Number of valid df rows:', df.shape[0])

result = curs.execute('SELECT MAX(`score_away`) FROM nfl').fetchone()
print('Max Away Score', result[0])

# Now go back to a Pandas dataframe from SQL query
# e.g. db_create_dataframe()
df_sql_query = pd.read_sql_query(query, conn)
# Down selecting the columns we want to grab from db to df
df = pd.DataFrame(df_sql_query, columns=['date', 'score_away'])
print('back to df:\n', df.head(3))

# Plot w/ Pandas abstraction layer over matplotlib
# simply provide the name of columns/series/numpy array wrappers
# Observed Temperature vs Time
df.plot('date', 'score_away')
# # call matplotlib plt show() like always
plt.show()
