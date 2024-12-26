from flask import Flask, render_template, request
from scraper import run_scraper

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    # Grab user input from the form
    keyword = request.form.get('keyword', '').strip()
    if not keyword:
        return "Please enter a valid keyword."

    # Run the scraper
    run_scraper(keyword)

    # Return a simple confirmation
    return f"Scraping complete for keyword: {keyword}. Check the 'downloads' folder for results."

if __name__ == '__main__':
    # For local testing only
    app.run(debug=True)
