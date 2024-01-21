from yt_dlp import YoutubeDL

options = {"verbose": True}
urls = [
    "https://www.youtube.com/watch?v=sqPylfqIQFw&list=PLGaZ4mS4kbxngzCztJ3FDo-mnndWlQQn7",
    "PLj_Goi54wf0eJfmEAU7HHieNM22axyQ5c",
]
with YoutubeDL(options) as ydl:
    ydl.download(urls)
