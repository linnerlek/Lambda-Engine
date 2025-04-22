import dash
from dash import Dash, html, dcc, callback, Output, Input, State, no_update
import dash_cytoscape as cyto
from urllib.parse import urlparse, parse_qs
from argparse import ArgumentParser

import os

from Lambda import get_initial_tree, get_next_tree, get_next_tree_after_math
from Lambda import tree2dict, to_string, json2tree
from styles import cytoscape_stylesheet
import re

cyto.load_extra_layouts()
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Lambda Engine"


# --------- Helpers ---------
def compute_subtree_width(node, base_width=120):
    if not node.get("children"):
        return base_width
    return sum(compute_subtree_width(child, base_width) for child in node["children"])


def json_to_cytoscape_elements(node_data, parent_id=None, elements=None, x=0, y=0, x_offset=120, y_offset=100):
    if elements is None:
        elements = []

    node_id = node_data["nodeid"]
    node_type = node_data["type"]
    beta_status = node_data.get("beta")

    label = ""
    node_class = "default-node"
    if node_type == "lambda":
        label = node_data["var"]
        node_class = "lambda-node"
    elif node_type == "apply":
        node_class = "apply-node"
        if beta_status == "YES":
            node_class += " apply-yes"
        elif beta_status == "NO":
            node_class += " apply-no"
    elif node_type in ["name", "num", "op"]:
        label = node_data["value"]
        node_class = f"{node_type}-node"

    # Add current node
    elements.append({
        "data": {
            "id": node_id,
            "label": label,
            "type": node_type,
            "beta": beta_status,
            "var": node_data.get("var"),
            "value": node_data.get("value"),
            "class": node_class,
        },
        "position": {"x": x, "y": y},
        "classes": node_class,
    })

    if parent_id:
        elements.append({
            "data": {
                "source": parent_id,
                "target": node_id,
                "id": f"edge_{parent_id}_{node_id}",
            }
        })

    # Recurse into children
    children = node_data.get("children", [])
    if children:
        if len(children) == 2:
            # Dynamically expand offset for wider subtrees
            left_width = compute_subtree_width(children[0])
            right_width = compute_subtree_width(children[1])

            new_offset = max(x_offset, (left_width + right_width) // 2)

            json_to_cytoscape_elements(children[0], node_id, elements, x - new_offset, y + y_offset, x_offset, y_offset)
            json_to_cytoscape_elements(children[1], node_id, elements, x + new_offset, y + y_offset, x_offset, y_offset)

        elif len(children) == 1:
            json_to_cytoscape_elements(children[0], node_id, elements, x, y + y_offset, x_offset, y_offset)

    return elements


def get_md_file_content(filename):
    with open(f'assets/{filename}', 'r') as file:
        return file.read()


# --------- Layout ---------
app.layout = html.Div([
    dcc.Location(id='url'),
    dcc.Store(id='tree'),
    dcc.Store(id='prevtrees'),
    html.Div(className="header", children=[
        #html.Img(src=app.get_asset_url('lambda-logo.png'), className="logo"),
        html.H1("Lambda Engine", className="title")
    ]),
    html.Div(id="app-container", children=[
        html.Div(className="left-section", children=[
            html.Div(className="input-container", children=[
                html.Button('Back', id='back', className="button"),
                dcc.Input(id='lambdaex', type='text', placeholder='Enter expression...', className="text-input"),
                html.Button('Submit', id='submit', className="button"),
                html.Button('Reset', id='reset', className="button"),
                dcc.ConfirmDialog(id='parseerror', message='Parse Error!'),
            ]),
            cyto.Cytoscape(
                id='cytoscape-graph',
                layout={'name': 'preset'},
                style={'width': '100%', 'height': '600px'},
                elements=[],
                stylesheet=cytoscape_stylesheet,
                userZoomingEnabled=True,
                userPanningEnabled=True
            ),
            html.P(id='stringtree', className="string-output")
        ]),
        html.Div(className="divider", id="divider"),
        html.Div(className="right-section", children=[
            html.Div(id="documentation-placeholder", children=[
                html.A("Documentation", id="open-docs", href="#"),
                html.A("Examples", id="open-queries", href="#")
            ]),
        ])
    ]),
    html.Div(id="modal-docs", className="modal", style={"display": "none"}, children=[
        html.Div(className="modal-content", children=[
            html.Div(id="doc-close-container", children=[
                html.Button("Close", id="close-docs-btn")
            ]),
            html.Div(id="docs-body", className="markdown-content")
        ])
    ]),
    html.Div(id="modal-queries", className="modal", style={"display": "none"}, children=[
        html.Div(className="modal-content", children=[
            html.Div(id="query-close-container", children=[
                html.Button("Close", id="close-queries-btn")
            ]),
            html.Div(id="queries-body", className="markdown-content")
        ])
    ])
])

@callback(
    [Output("modal-docs", "style"), Output("docs-body", "children")],
    [Input("open-docs", "n_clicks"), Input("close-docs-btn", "n_clicks")],
    prevent_initial_call=True
)
def toggle_docs_modal(open_clicks, close_clicks):
    ctx = dash.callback_context
    if ctx.triggered[0]['prop_id'].split('.')[0] == "open-docs":
        return {"display": "flex"}, dcc.Markdown(get_md_file_content("instructions.md"))
    return {"display": "none"}, ""


@callback(
    [Output("modal-queries", "style"),
     Output("queries-body", "children")],
    [Input("open-queries", "n_clicks"),
     Input("close-queries-btn", "n_clicks")],
    prevent_initial_call=True
)
def toggle_queries_modal(open_clicks, close_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return {"display": "none"}, ""

    trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger == "open-queries":
        raw_md = get_md_file_content("queries.md")
        parts = re.split(r'(```.*?```)', raw_md, flags=re.DOTALL)
        content = []
        index = 1

        for part in parts:
            part = part.strip()
            if part.startswith("```") and part.endswith("```"):
                code = part.strip("`").strip()
                content.append(
                    html.Pre(
                        code,
                        className='query-block',
                        id={'type': 'query-block', 'index': index},
                        style={'cursor': 'pointer'}
                    )
                )
                index += 1
            else:
                content.append(dcc.Markdown(part, dangerously_allow_html=True))

        return {"display": "flex"}, content

    return {"display": "none"}, ""

@callback(
    Output("lambdaex", "value"),
    [Input({"type": "query-block", "index": dash.dependencies.ALL}, "n_clicks")],
    [State("queries-body", "children")],
    prevent_initial_call=True
)
def insert_query_block(clicks, children):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    triggered = ctx.triggered[0]["prop_id"]
    if "query-block" not in triggered:
        return dash.no_update

    triggered_id = eval(triggered.split(".")[0])
    idx = triggered_id["index"]

    # Check if this was an actual click (non-zero)
    if clicks[idx - 1] is None or clicks[idx - 1] == 0:
        return dash.no_update

    for element in children:
        if isinstance(element, dict) and element["type"] == "Pre":
            props = element.get("props", {})
            eid = props.get("id", {})
            if eid.get("type") == "query-block" and eid.get("index") == idx:
                return props.get("children")

    return dash.no_update



# ======== INPUT CALLBACKS ========
@callback(
    Output('tree', 'data', allow_duplicate=True),
    Output('prevtrees', 'data', allow_duplicate=True),
    Output('submit', 'disabled'),
    Output("parseerror", "displayed"),
    Input('submit', 'n_clicks'), 
    State('lambdaex', 'value'),
    prevent_initial_call=True
)
def submit_initial_expression(n_clicks, value):
    tree = get_initial_tree(value)
    if tree["status"] == "OK":
        return tree, [tree], True, False
    else:
        print("ERROR parsing lambda expression", tree["message"])
        return None, None, False, True
    
@callback(
    Output('tree', 'data', allow_duplicate=True),
    Output('prevtrees', 'data', allow_duplicate=True),
    Output('submit', 'disabled', allow_duplicate=True),
    Output("parseerror", "displayed", allow_duplicate=True),
    Input('url', 'href'), 
    prevent_initial_call=True
)
def submit_initial_expression_url(href):
    if href:
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        
        if 'expression' in query_params:
            expression = query_params['expression'][0]
            expression = str(expression).replace('%20', ' ')
            tree = get_initial_tree(expression)
            if tree["status"] == "OK":
                return tree, [tree], True, False
            else:
                print("ERROR parsing lambda expression", tree["message"])
                return None, None, False, True
    
    return None, None, False, False

# ======== VISUALIZATION CALLBACKS ========
@callback(
    Output('cytoscape-graph', 'elements'), 
    Output('stringtree', 'children'), 
    Input('tree', 'data'),
    prevent_initial_call=True
)
def retrieve_data_from_store(tree):
    if tree is None:
        return [], ""
        
    root_data = tree['expr_tree_json']
    elements = json_to_cytoscape_elements(root_data)
    
    # create text representation
    stringtree = ''
    if type(tree) == dict:
        stringtree = json2tree(tree['expr_tree_json'])
        stringtree = to_string(stringtree)
    
    return elements, stringtree

def build_cytoscape_elements(node_data, parent_id=None, elements=None):
    if elements is None:
        elements = []
    
    node_id = node_data['nodeid']
    node_type = node_data['type']
    beta_status = node_data.get('beta')
    
    if node_type == 'lambda':
        label = f"{node_data['var']}"
        node_class = 'lambda-node'
    elif node_type == 'apply':
        label = ""
        node_class = 'apply-node'
        if beta_status == 'YES':
            node_class += ' apply-yes'
        elif beta_status == 'NO':
            node_class += ' apply-no'
    elif node_type == 'name':
        label = f"{node_data['value']}"
        node_class = 'name-node'
    elif node_type == 'num':
        label = f"{node_data['value']}"
        node_class = 'num-node'
    elif node_type == 'op':
        label = f"{node_data['value']}"
        node_class = 'op-node'
    else:
        label = node_type
        node_class = 'default-node'
    
    node = {
        'data': {
            'id': node_id,
            'label': label,
            'type': node_type,
            'beta': beta_status,
            'var': node_data.get('var'),
            'value': node_data.get('value'),
            'class': node_class
        },
        'classes': node_class
    }
    
    elements.append(node)
    
    if parent_id:
        elements.append({
            'data': {
                'source': parent_id,
                'target': node_id,
                'id': f'edge_{parent_id}_{node_id}'
            }
        })
    
    children = node_data.get('children', [])
    for child in children:
        build_cytoscape_elements(child, node_id, elements)
    
    return elements

# ======== INTERACTION CALLBACKS ========
@callback(
    Output('tree', 'data', allow_duplicate=True),
    Output('prevtrees', 'data', allow_duplicate=True),
    Input('cytoscape-graph', 'tapNodeData'), 
    State('tree', 'data'),
    State('prevtrees', 'data'),
    prevent_initial_call=True
)
def select_node(node_data, tree, prevtrees):
    if tree is None or node_data is None:
        return no_update, no_update
        
    selected_node_id = node_data['id']
    selected_node_type = node_data['type']
    selected_node_beta = node_data.get('beta')
    
    # perform beta reduction on eligible nodes
    if selected_node_type == 'apply' and selected_node_beta == "YES":
        tree = get_next_tree(tree['expr_tree_json'], selected_node_id)
        tree = tree2dict(tree)
        tree = {"status": "OK", "expr_tree_json": tree}
        
        if prevtrees == [] or prevtrees is None:
            prevtrees = [tree]
        else:
            prevtrees.append(tree)
            
        return tree, prevtrees
    
    # evaluate arithmetic expressions
    elif selected_node_type == 'op':
        tree = get_next_tree_after_math(tree['expr_tree_json'], selected_node_id)
        tree = tree2dict(tree)
        tree = {"status": "OK", "expr_tree_json": tree}
        
        if prevtrees == [] or prevtrees is None:
            prevtrees = [tree]
        else:
            prevtrees.append(tree)
            
        return tree, prevtrees
        
    return no_update, no_update

@callback(
    Output('tree', 'data', allow_duplicate=True),
    Output('prevtrees', 'data', allow_duplicate=True),
    Input('back', 'n_clicks'), 
    State('tree', 'data'),
    State('prevtrees', 'data'),
    prevent_initial_call=True
)
def go_back(n_clicks, tree, prevtrees):
    if prevtrees and len(prevtrees) > 1:
        pt = prevtrees.pop(-1)
        return prevtrees[-1], prevtrees
    return no_update, no_update

@callback(
    Output('back', 'disabled'),
    Input('prevtrees', 'data'),
    prevent_initial_call=True
)
def set_back_button_disabled_state(prevtrees):
    if prevtrees != None:
        return len(prevtrees) == 1
    else:
        return True
    
@callback(
    Output('prevtrees', 'data', allow_duplicate=True),
    Output('tree', 'data', allow_duplicate=True),
    Output('back', 'disabled', allow_duplicate=True),
    Output('lambdaex', 'value', allow_duplicate=True),
    Output('submit', 'disabled', allow_duplicate=True),
    Input('reset', 'n_clicks'),  
    prevent_initial_call=True
)
def reset(n_clicks):
    return [], None, True, '', False

# ======== MAIN ========
if __name__ == '__main__':
    parser = ArgumentParser(
        prog='Lambda Engine',
        description='Process Lambda calculus and provides a graphical view of the steps of the process'
    )
    parser.add_argument('--hostname', default='localhost')
    parser.add_argument('--port', default='8081')
    args = parser.parse_args()

    app.run(debug=False, host=args.hostname, port=args.port)