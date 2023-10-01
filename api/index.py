import os
from urllib.parse import urlparse
import requests
import openai
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
import json
import re

app = Flask(__name__)

# Load environment variables from .env file
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Set your OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")
openai.api_key = openai_api_key

def is_url(input_string):
    try:
        result = urlparse(input_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# Function to scrape text from a website
def scrape_text_from_url(url):
    response = requests.get(url)
    if response.status_code != 200:
        return "Error: Could not retrieve content from URL."
    soup = BeautifulSoup(response.text, "html.parser")
    paragraphs = soup.find_all("p")
    text = " ".join([p.get_text() for p in paragraphs])
    return text


def correct_json(response_data):
    """
    Corrects the JSON response from OpenAI to be valid JSON
    """
    response_data = re.sub(
        r',\s*}', '}',
        re.sub(r',\s*]', ']',
               re.sub(r'(\w+)\s*:', r'"\1":', response_data)))
    return response_data


@app.route("/api/get_graph_data", methods=["POST"])
def get_graph_data():
    try: 
        user_input = request.json.get("user_input", "")
        if not user_input:
            return jsonify({"error": "No input provided"}), 400
        
        # Check if the user input is a URL
        if is_url(user_input):
            user_input = scrape_text_from_url(user_input)

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {
                    "role": "user",
                    "content": f"I want to understand the following content by visualizing it as a knowledge graph: '{user_input}'. Please use the provided color specifications."
,
                }
            ],
            functions=[
                {
                    "name": "knowledge_graph",
                    "description": "Construct a knowledge graph from articles with distinct nodes each measuring 300px by 50px. Centralize the main node and arrange others radially. Ensure clarity by spacing nodes and edges. Every node must link to another. The edges should be named with predicates. Highlight: Main Points (HEX: 483698), Sub Points (HEX: 005EB8), Details (HEX: 470A68), Extra Info (HEX: 0091DA), References (HEX: 6D2077), and Misc. (HEX: 00A3A1). Adjust text color for legibility on dark nodes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metadata": {
                                "type": "object",
                                "properties": {
                                    "createdDate": {"type": "string"},
                                    "lastUpdated": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            },
                            "nodes": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "label": {"type": "string"},
                                        "type": {"type": "string"},
                                        "color": {"type": "string"},  # Added color property
                                        "properties": {
                                            "type": "object",
                                            "description": "Additional attributes for the node",
                                        },
                                        "position_x": {"type": "number"},
                                        "position_y": {"type": "number"},
                                    },
                                    "required": [
                                        "id",
                                        "label",
                                        "type",
                                        "color",
                                        "position_x",
                                        "position_y"
                                    ],  # Added color to required
                                },
                            },
                            "edges": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "from": {"type": "string"},
                                        "to": {"type": "string"},
                                        "relationship": {"type": "string"},
                                        "direction": {"type": "string"},
                                        "color": {"type": "string"},  # Added color property
                                        "properties": {
                                            "type": "object",
                                            "description": "Additional attributes for the edge",
                                        },
                                    },
                                    "required": [
                                        "from",
                                        "to",
                                        "relationship",
                                        "color",
                                    ],  # Added color to required
                                },
                            },
                        },
                        "required": ["nodes", "edges"],
                    },
                }
            ],
            function_call={"name": "knowledge_graph"},
        )
        response_data = completion.choices[0]["message"]["function_call"]["arguments"]
        response_data = correct_json(response_data)
        # print(response_data) this has direction: "Outgoing" for edges
        nodes, edges = create_nodes_edges(response_data)
        return jsonify({"elements": {"nodes": nodes, "edges": edges}})
    except Exception as e:
        return jsonify({"error": "Something went wrong"}), 500

def create_nodes_edges(data):
    try:
        response_dict = json.loads(data)
        nodes = []
        edges = []

        for node in response_dict["nodes"]:
            nodes.append({
                "id": node["id"],
                "position": {"x": node["position_x"], "y": node["position_y"]},
                "style": {"background": node["color"]},
                "data": {"label": node["label"]},
                "draggable": True,
                "selectable": False,
                "deletable": False
            })

        for edge in response_dict["edges"]:
            edges.append({
                "id": f"{edge['from']}-{edge['to']}",
                "source": edge["from"],
                "target": edge["to"],
                "label": edge["relationship"],
                "type": "default",
                "style": {"stroke": edge["color"]}
            })

        return nodes, edges
    except Exception as e:
        print(e)
        return [], []
