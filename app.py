from dash import Dash, html, dcc, callback, Output, Input, State, no_update
from argparse import ArgumentParser
from urllib.parse import urlparse, parse_qs
import dash_cytoscape as cyto

from Lambda import get_initial_tree, get_next_tree, get_next_tree_after_math
from Lambda import tree2dict, to_string, json2tree
from styles import cytoscape_stylesheet, styles

cyto.load_extra_layouts()

# ======== TREE VISUALIZATION ========
def json_to_cytoscape_elements(node_data, parent_id=None, elements=None, level=0, x=0, y=0, x_offset=120, y_offset=100, level_positions=None):
    if elements is None:
        elements = []
    
    if level_positions is None:
        level_positions = {}
    
    node_id = node_data['nodeid']
    node_type = node_data['type']
    beta_status = node_data.get('beta')
    
    # minimum pixel distance between nodes at same level
    min_separation = 60
    
    if y not in level_positions:
        level_positions[y] = []
    
    # check if node overlaps with existing nodes
    overlap_detected = False
    for pos in level_positions[y]:
        if abs(pos - x) < min_separation:
            overlap_detected = True
            break
    
    # adjust position if overlap occurs
    if overlap_detected and parent_id:
        y += y_offset / 2
        
        if y not in level_positions:
            level_positions[y] = []
    
    level_positions[y].append(x)
    
    # determine node style based on type
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
    
    # create node data structure
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
        'position': {
            'x': x,
            'y': y
        },
        'classes': node_class
    }
    
    elements.append(node)
    
    # add edge if this is not the root
    if parent_id:
        elements.append({
            'data': {
                'source': parent_id,
                'target': node_id,
                'id': f'edge_{parent_id}_{node_id}'
            }
        })
    
    children = node_data.get('children', [])
    child_count = len(children)
    
    # recursively add children with specific positioning
    if child_count == 2:
        # left child at 45° angle
        json_to_cytoscape_elements(
            children[0], 
            node_id, 
            elements, 
            level + 1, 
            x - x_offset,
            y + y_offset,
            x_offset,
            y_offset,
            level_positions
        )
        
        # right child at 45° angle
        json_to_cytoscape_elements(
            children[1], 
            node_id, 
            elements, 
            level + 1, 
            x + x_offset,
            y + y_offset,
            x_offset,
            y_offset,
            level_positions
        )
    elif child_count == 1:
        # single child directly below
        json_to_cytoscape_elements(
            children[0], 
            node_id, 
            elements, 
            level + 1, 
            x,
            y + y_offset,
            x_offset,
            y_offset,
            level_positions
        )
    
    return elements

# ======== APP SETUP ========
app = Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div(children=[
    dcc.Store(id='tree'),
    dcc.Store(id='prevtrees'),
    dcc.Store(id='has-zoomed', data=False),
    dcc.Location(id='url'),
    html.H2(children='Lambda Engine', style=styles['header']),
    html.Div(children=[
        html.Button('Back', id='back', style=styles['button']),
        dcc.Input(
            id='lambdaex', 
            type='text', 
            value='', 
            placeholder='Enter an expression...', 
            style=styles['input']
        ),
        html.Button('Submit', id='submit', style=styles['button']),
        html.Button('Reset', id='reset', style=styles['button']),
        dcc.ConfirmDialog(id='parseerror', message='Parse Error!'),
    ], style=styles['controls_container']),
    html.Div(children=[
        cyto.Cytoscape(
            id='cytoscape-graph',
            layout={'name': 'preset', 'animate': False},
            style=styles['cytoscape'],
            elements=[],
            stylesheet=cytoscape_stylesheet,
            boxSelectionEnabled=False,
            autounselectify=False,
            userZoomingEnabled=True,
            userPanningEnabled=True,
            zoom=1,
            minZoom=0.2,
            maxZoom=3
        ),
    ], style=styles['graph_container']),
    html.Div(children=[
        html.P(id='stringtree'),
    ], style=styles['footer'])
], style=styles['page_container'])

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
    # process user submitted expression
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
    # parse expression from url parameter using standard library
    if href:
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        
        if 'expression' in query_params:
            expression = query_params['expression'][0]  # parse_qs returns lists
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
    # convert tree data to visual elements
    if tree is None:
        return [], ""
        
    root_data = tree['expr_tree_json']
    elements = json_to_cytoscape_elements(root_data, level_positions={})
    
    # generate text representation
    stringtree = ''
    if type(tree) == dict:
        stringtree = json2tree(tree['expr_tree_json'])
        stringtree = to_string(stringtree)
    
    return elements, stringtree

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
    # handle user clicking on tree nodes
    if tree is None or node_data is None:
        return no_update, no_update
        
    selected_node_id = node_data['id']
    selected_node_type = node_data['type']
    selected_node_beta = node_data.get('beta')
    
    # handle beta reduction for apply nodes
    if selected_node_type == 'apply' and selected_node_beta == "YES":
        tree = get_next_tree(tree['expr_tree_json'], selected_node_id)
        tree = tree2dict(tree)
        tree = {"status": "OK", "expr_tree_json": tree}
        
        if prevtrees == [] or prevtrees is None:
            prevtrees = [tree]
        else:
            prevtrees.append(tree)
            
        return tree, prevtrees
    
    # handle arithmetic operations
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
    # navigate to previous state in history
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
    # disable back button when at initial state
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
    # clear all state and return to initial screen
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

    app.run_server(debug=False, host=args.hostname, port=args.port)