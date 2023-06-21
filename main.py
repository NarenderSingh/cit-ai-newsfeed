# Import necessary packages for API.
from fastapi import FastAPI, Path, HTTPException, status
from fastapi import Query
app = FastAPI()

#Importing other packages.
import requests
import os
from dotenv import load_dotenv
from langchain import OpenAI
from langchain import PromptTemplate
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.prompts import load_prompt
from langchain.chains import LLMChain
from newspaper import Article
from typing import Optional
import json

#Loading the keys from environment.
# load_dotenv("./.env", verbose=True)
# BING_KEY = os.getenv('BING_KEY')
# OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

#Creating an instance of FASTAPI().
app = FastAPI()

# Initializing LLM
llm = OpenAI(temperature=0, openai_api_key="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")

# Creating Prompt Template/s
summary_prompt = load_prompt("template_file.json")

# Defining sub-functions
def bing_news_web_search(query: str, freshness: str, num_articles: int, market: str) -> list[dict]:
    """This function makes calls to Bing News Search and returns a list of dictionaries."""
    # set parameters
    search_url = "https://api.bing.microsoft.com/v7.0/news/search"
    headers = {"Ocp-Apim-Subscription-Key": "39f3ee7173804f388464e160ec345e71"}
    params = {
        "q": query,
        "textDecorations": False,
        "textFormat": "HTML",
        "freshness": freshness,
        "count": num_articles}
    if market != None:
        params["mkt"] = market
    # get response
    response = requests.get(search_url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["value"]

def format_articles(articles_list: list[dict]) -> list[dict]:
    """This function formats results from the bing_news_web_search function."""
    for i in range(len(articles_list)):
        articles_list[i] = {x: articles_list[i][x] for x in ["name", "datePublished", "url", "provider", "description"]}
        articles_list[i]["provider"] = articles_list[i]["provider"][0]["name"]
    return articles_list

def retrieve_article_text(link: str) -> str:
    """This function when given a URL returns an article's text."""
    try:
        article = Article(link)
        article.download()
        article.parse()
        return article.text
    except:
        return None
    
def result_formatter(result: str) -> dict:
    summary_string = result.split('summary": "')[1]
    summary_string = summary_string.split('",\n    "alert"')[0]
    #summary_string = summary_string.replace('"', "'")
    alert_string = result.split('"alert": ')[1]
    alert_string = alert_string.split(',\n    "')[0]
    if alert_string == 'false':
        alert_string = False
    else:
        alert_string = True
    alert_content_string = result.split('"alert_content": "')[1]
    alert_content_string = alert_content_string.split('"\n}')[0]
    #alert_content_string = alert_content_string.replace('"', "'")
    return {"summary": summary_string,
            "alert": alert_string, "alert_content": alert_content_string}

def summarizer_alerter(article_text: str, alerts: str) -> dict:
    """Returns a dictionary with a summary, alert status and what has triggerred the alert. """
    if article_text == "":
            return {"summary": "Error: Article Text Not Retrievable",
                    "alert": "Error: Alert Not Available",
                    "alert_content": "Error: Alert Not Available"}
    final_summary_prompt = summary_prompt.format(news_article_text=article_text, alert_content=alerts)
    result = llm(final_summary_prompt)
    try:     
        return json.loads(result)
    except:
        try: 
            return result_formatter(result=result)
        except:
            return {"summary": "Error: Article Summary Not Available - Formatting Issue",
                    "alert": "Error: Alert Not Available",
                    "alert_content": "Error: Alert Not Available"}
    
def summarizer_alerter_errors(article_text: str, alerts: str) -> dict:
    """Returns a dictionary with a summary, alert status and what has triggerred the alert. """
    final_summary_prompt = summary_prompt.format(news_article_text=article_text, alert_content=alerts)
    results = llm(final_summary_prompt)
    print(results)
    return json.loads(results)

@app.get("/")
async def root():
    return {"message": "Hello World"}

#Defining end-point for curating news articles about a single topic
@app.get("/api")
def return_query(query: str, freshness: str, num_articles: int, 
                 market: Optional[str] = None, alerts: Optional[str] = None) -> list[dict]:
    articles_list = bing_news_web_search(query=query, freshness=freshness, 
                                         num_articles=num_articles, market=market)
    articles_list_formatted = format_articles(articles_list=articles_list)
    
    for i in range(len(articles_list_formatted)):
        article_text = retrieve_article_text(articles_list_formatted[i]["url"])
        summary_alert_dict = summarizer_alerter(article_text=article_text, alerts=alerts)
        if alerts == None and summary_alert_dict["alert"] != "Error: Alert Not Available":
            summary_alert_dict["alert"] = False
            summary_alert_dict["alert_content"] = ""
        articles_list_formatted[i].update(summary_alert_dict)
        
    return articles_list_formatted