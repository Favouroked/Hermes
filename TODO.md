Flow:
- User installs chrome extension
- Chrome extension shows place for user to add resume and preferences, also api key or url to local llama
- Chrome extension calls backend and gets some google query generated
- Chrome extension records the results and sends it to the backend. 
- if local llama, chrome extension calls it instead of openai
- User can click on auto-apply button on chrome extension
- Auto apply calls api to get job listings and open them. 
- If there is a form on the page, fill the form by generating answers based on resume.