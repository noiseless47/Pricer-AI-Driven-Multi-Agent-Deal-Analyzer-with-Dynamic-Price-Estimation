import logging
import queue
import threading
import time
import gradio as gr
from app.core.deal_agent_framework import DealAgentFramework
from app.agents.deals import Opportunity, Deal
from app.utils.log_formatting import reformat
import plotly.graph_objects as go

import os
import requests
import json        
from dotenv import load_dotenv
load_dotenv()



class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


def html_for(log_data):
    output = '<br>'.join(log_data[-18:])
    return f"""
    <div id="scrollContent" style="height: 400px; overflow-y: auto; border: 1px solid #ccc; background-color: #222229; padding: 10px;">
    {output}
    </div>
    """


def setup_logging(log_queue):
    handler = QueueHandler(log_queue)
    formatter = logging.Formatter(
        "[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %z",
    )
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


LLAMA_ENDPOINT = "http://localhost:11434/api/generate"  # OLLAMA endpoint
LLAMA_MODEL = "llama3.2"                                 # Your model name


# ======================================================
# CALL LOCAL LLaMA
# ======================================================
def call_llama(prompt):

    # 1. Build correct payload based on endpoint
    if "11434" in LLAMA_ENDPOINT:   # OLLAMA
        payload = {"model": LLAMA_MODEL, "prompt": prompt, "stream": False}

    elif "/v1/" in LLAMA_ENDPOINT:  # LM STUDIO (OpenAI format)
        payload = {
            "model": LLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }

    else:                            # FALLBACK (llama.cpp)
        payload = {"model": LLAMA_MODEL, "prompt": prompt}

    # Call model
    r = requests.post(LLAMA_ENDPOINT, json=payload)
    raw = r.text.strip()

    # 2. Try direct JSON parse
    try:
        data = r.json()
        return (
            data.get("response") or
            (data.get("choices", [{}])[0].get("message", {}).get("content")) or
            data.get("content")
        )
    except:
        pass

    # 3. FIX multi-chunk JSON (Ollama sometimes outputs two JSON blocks)
    cleaned = raw.replace("}\n{", "},{").replace("}{", "},{")
    cleaned = "[" + cleaned + "]"

    try:
        chunk = json.loads(cleaned)[0]
        return (
            chunk.get("response") or
            chunk.get("content") or
            (chunk.get("choices", [{}])[0].get("message", {}).get("content"))
        )
    except:
        return f"⚠ Invalid LLM output:\n{raw}"

def reasons_for_item(desc):
    prompt = f"""
Give 3–5 short bullet points on why someone should BUY this product:

{desc}

Keep it crisp, simple and benefit-focused.
"""
    return call_llama(prompt)


def reasons_for_all_items():
    with open(DealAgentFramework.MEMORY_FILENAME, "r", encoding="utf-8") as f:
        mem = json.load(f)

    last_items = mem[-5:]

    html = """
    <style>
    .card {
        background: #2a2a31;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #3b3b44;
    }
    .title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 8px;
        color: #ffffff;
    }
    .subtitle {
        font-size: 13px;
        margin-bottom: 8px;
        color: #c7c7c7;
    }
    .bullet {
        font-size: 13px;
        margin-left: 12px;
        color: #e0e0e0;
    }
    </style>

    <h2>🧠 LLM Analysis — Reasons to Buy (Last 5 Deals)</h2>
    """

    for item in last_items:
        desc = item["deal"]["product_description"]
        reason = reasons_for_item(desc)   # <- KEEP THIS

        bullets = ""
        for line in reason.split("\n"):
            if line.strip():
                bullets += f"<div class='bullet'>• {line.strip()}</div>"

        short_title = desc[:70] + "..." if len(desc) > 70 else desc

        html += f"""
        <div class='card'>
            <div class='title'>{short_title}</div>
            <div class='subtitle'>AI-generated key reasons to consider buying this product:</div>
            {bullets}
        </div>
        """

    return html




class App:

    def __init__(self):
        self.agent_framework = None

    def get_agent_framework(self):
        if not self.agent_framework:
            self.agent_framework = DealAgentFramework()
            self.agent_framework.init_agents_as_needed()
        return self.agent_framework

    def run(self):
    
        # ===============================
        # 1. INTERNAL FUNCTIONS (must appear first)
        # ===============================
        
        def table_for(opps):
            return [
                [
                    opp.deal.product_description,
                    f"₹{opp.deal.price:.2f}",
                    f"₹{opp.estimate:.2f}",
                    f"₹{opp.discount:.2f}",
                    opp.deal.url,
                ]
                for opp in opps
            ]
        
        def update_output(log_data, log_queue, result_queue):
            initial_result = table_for(self.get_agent_framework().memory)
            final_result = None
            while True:
                try:
                    message = log_queue.get_nowait()
                    log_data.append(reformat(message))
                    yield log_data, html_for(log_data), final_result or initial_result
                except queue.Empty:
                    try:
                        final_result = result_queue.get_nowait()
                        yield log_data, html_for(log_data), final_result or initial_result
                    except queue.Empty:
                        if final_result is not None:
                            break
                        time.sleep(0.1)
        
        def get_plot():
            documents, vectors, colors = DealAgentFramework.get_plot_data(max_datapoints=1000)
            fig = go.Figure(
                data=[go.Scatter3d(
                    x=vectors[:, 0],
                    y=vectors[:, 1],
                    z=vectors[:, 2],
                    mode='markers',
                    marker=dict(size=2, color=colors, opacity=0.7),
                )]
            )
            fig.update_layout(
                scene=dict(
                    xaxis_title='x',
                    yaxis_title='y',
                    zaxis_title='z',
                    aspectmode='manual',
                    aspectratio=dict(x=2.2, y=2.2, z=1),
                    camera=dict(eye=dict(x=1.6, y=1.6, z=0.8))
                ),
                height=350,
                margin=dict(r=5, b=1, l=5, t=2)
            )
            return fig
        
        def do_run():
            new_opportunities = self.get_agent_framework().run()
            return table_for(new_opportunities)
        
        def run_with_logging(initial_log_data):
            log_queue = queue.Queue()
            result_queue = queue.Queue()
            setup_logging(log_queue)
        
            def worker():
                result = do_run()
                result_queue.put(result)
        
            thread = threading.Thread(target=worker)
            thread.start()
        
            for log_data, output, final_result in update_output(initial_log_data, log_queue, result_queue):
                yield log_data, output, final_result
        
        def do_select(selected_index: gr.SelectData):
            opportunities = self.get_agent_framework().memory
            row = selected_index.index[0]
            opportunity = opportunities[row]
            self.get_agent_framework().planner.messenger.alert(opportunity)
        
        def filter_status_update(*args):
            """Show a status update when filters change"""
            return "✓ Filters updated - Click refresh to apply"
        
        # ===============================
        # 2. UI STARTS HERE
        # ===============================
        
        with gr.Blocks(title="The Price is Right", fill_width=True) as ui:
        
            # TOP FILTER PANEL
            with gr.Row(equal_height=True):
        
                # ------ LEFT FILTERS ------
                with gr.Column():
        
                    gr.Markdown("### Sort Preferences")
                    preference = gr.CheckboxGroup(
                        choices=["Least Price", "Most Discount", "Newest Deals", "Date of Arrival"],
                        value=[],
                        interactive=True
                    )
        
                    gr.Markdown("### Time Constraint")
                    time_constraint = gr.CheckboxGroup(
                        choices=["Within 1 Day", "2-3 Days", "This Week", "This Month", "Anytime"],
                        value=["Anytime"],
                        interactive=True
                    )
        
                    gr.Markdown("### Price Range")
                    price_filter = gr.CheckboxGroup(
                        choices=["< ₹1,000", "< ₹10,000", "₹10,000 - ₹20,000", "> ₹25,000"],
                        value=[],
                        interactive=True
                    )
        
                    gr.Markdown("### Ratings")
                    ratings_filter = gr.CheckboxGroup(
                        choices=["4★ & above", "3★ - 4★", "No Rating Filter"],
                        value=["No Rating Filter"],
                        interactive=True
                    )
        
                    gr.Markdown("### Delivery")
                    delivery_filter = gr.CheckboxGroup(
                        choices=["Free Delivery", "No Filter"],
                        value=["No Filter"],
                        interactive=True
                    )
        
                    gr.Markdown("### Manufacturing Age")
                    mfg_filter = gr.CheckboxGroup(
                        choices=["Last 1 Year", "Last 2 Years", "No Filter"],
                        value=["No Filter"],
                        interactive=True
                    )
        
                # ------ RIGHT FILTERS ------
                with gr.Column():
        
                    gr.Markdown("### Domains")
                    domain = gr.CheckboxGroup(
                        choices=[
                            "All", "Mobiles", "Laptops", "Headphones", "Electronics", "Gaming",
                            "Clothing", "Fashion", "Shoes", "Watches", "Home & Kitchen", "Sports",
                            "Beauty & Personal Care", "Grocery", "Appliances", "Tablets",
                            "Cameras", "Computer Accessories", "TVs", "Books", "Furniture",
                            "Toys", "Smartwatches", "Wearables"
                        ],
                        value=["All"],
                        interactive=True
                    )
        
                    # Bubble chart in accordion (safe)
                    with gr.Accordion("Category Popularity Visual", open=False):
        
                        import plotly.express as px
                        import pandas as pd
        
                        df = pd.DataFrame({
                            "category": ["Mobiles", "Laptops", "Headphones", "Clothing", "Gaming", "Home"],
                            "value": [50, 40, 30, 20, 35, 25],
                        })
        
                        bubble_fig = px.scatter(
                            df,
                            x="category",
                            y="value",
                            size="value",
                            color="category",
                            size_max=60,
                            height=320
                        )
        
                        bubble_fig.update_layout(
                            paper_bgcolor="#222229",
                            plot_bgcolor="#222229",
                            font=dict(color="white"),
                            height=320,
                            margin=dict(l=10, r=10, t=10, b=10)
                        )
        
                        bubble_plot = gr.Plot(value=bubble_fig, show_label=False)
        
            # Filter status indicator
            filter_status = gr.Textbox(
                value="",
                show_label=False,
                interactive=False,
                visible=True,
                container=False
            )
        
            # REFRESH BUTTON
            with gr.Row():
                refresh_button = gr.Button("🔄 Apply Filters & Refresh Deals", variant="primary")
        
            log_data = gr.State([])
        
            # TABLE
            with gr.Row():
                opportunities_dataframe = gr.Dataframe(
                    headers=["Deals found so far", "Price", "Estimate", "Discount", "URL"],
                    wrap=True,
                    column_widths=[6, 1, 1, 1, 3],
                    row_count=10,
                    col_count=5,
                    max_height=400,
                    interactive=False
                )


            with gr.Accordion("LLM Analysis — Reasons to Buy ", open=False):
            
                reasons_btn = gr.Button("Generate Reasons for All Deals")
                reasons_output = gr.HTML("Click the button to generate insights.\n")
            
                reasons_btn.click(
                    fn=reasons_for_all_items,
                    inputs=None,
                    outputs=reasons_output
                )

        
            # LOGS LEFT + 3D PLOT RIGHT
            with gr.Row():
        
                with gr.Column(scale=1):
                    logs = gr.HTML()
        
                with gr.Column(scale=1):
                    plot = gr.Plot(value=get_plot(), show_label=False)
        
        
            # ===============================
            # 3. EVENTS - Connect all filters
            # ===============================
            
            # Make all checkboxes show status update on change
            all_filters = [
                preference, time_constraint, price_filter, 
                ratings_filter, delivery_filter, mfg_filter, domain
            ]
            
            for filter_component in all_filters:
                filter_component.change(
                    fn=filter_status_update,
                    inputs=all_filters,
                    outputs=filter_status
                )
            
            # Main refresh and load events
            ui.load(
                fn=run_with_logging, 
                inputs=[log_data], 
                outputs=[log_data, logs, opportunities_dataframe]
            )
        
            timer = gr.Timer(value=300, active=True)
            timer.tick(
                fn=run_with_logging, 
                inputs=[log_data], 
                outputs=[log_data, logs, opportunities_dataframe]
            )
        
            refresh_button.click(
                fn=run_with_logging, 
                inputs=[log_data], 
                outputs=[log_data, logs, opportunities_dataframe]
            )
        
            opportunities_dataframe.select(do_select)
        
        
        ui.launch(share=False, inbrowser=True)


if __name__ == "__main__":
    App().run()