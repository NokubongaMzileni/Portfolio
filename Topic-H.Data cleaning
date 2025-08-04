import pandas as pd

# Load the dataset
df = pd.read_csv('student_scores.csv')
print("Original Data:\n", df.head())
print("Shape:", df.shape)

# Show rows with missing values
print("Missing values per column:\n", df.isnull().sum())

# Remove rows with missing values
df_cleaned = df.dropna()

# Fill missing scores with mean
df['score'] = df['score'].fillna(df['score'].mean())

# Convert 'score' to numeric (if stored as object/string)
df_cleaned['score'] = pd.to_numeric(df_cleaned['score'], errors='coerce')

# Remove duplicate rows
df_cleaned = df_cleaned.drop_duplicates()

import matplotlib.pyplot as plt

# Compare number of rows
print("Before:", df.shape)
print("After:", df_cleaned.shape)

# Plot comparison
counts = [df.shape[0], df_cleaned.shape[0]]
labels = ['Before Cleaning', 'After Cleaning']

plt.bar(labels, counts, color=['red', 'green'])
plt.title('Dataset Size Before vs After Cleaning')
plt.ylabel('Number of Rows')
plt.show()

