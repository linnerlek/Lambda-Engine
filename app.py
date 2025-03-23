from dash import Dash, html, dcc, callback, Output, Input, State, no_update
from argparse import ArgumentParser
from urllib.parse import urlparse, parse_qs
import dash_cytoscape as cyto

from Lambda import get_initial_tree, get_next_tree, get_next_tree_after_math
from Lambda import tree2dict, to_string, json2tree
from styles import cytoscape_stylesheet, styles

cyto.load_extra_layouts()

# ======== TREE VISUALIZATION ========
def json_to_cytoscape_elements(node_data, parent_id=None, elements=None, level=0, x=0, y=0, x_offset=120, y_offset=100, level_positions=None, node_widths=None):
    if elements is None:
        elements = []
    
    if level_positions is None:
        level_positions = {}
    
    if node_widths is None:
        node_widths = {}
    
    node_id = node_data['nodeid']
    node_type = node_data['type']
    beta_status = node_data.get('beta')
    
    # set node appearance based on type
    if node_type == 'lambda':
        label = f"{node_data['var']}"
        node_class = 'lambda-node'
        node_width = max(50, len(label) * 10)  # wider for longer text
    elif node_type == 'apply':
        label = ""
        node_class = 'apply-node'
        node_width = 40
        if beta_status == 'YES':
            node_class += ' apply-yes'
        elif beta_status == 'NO':
            node_class += ' apply-no'
    elif node_type == 'name':
        label = f"{node_data['value']}"
        node_class = 'name-node'
        node_width = max(50, len(label) * 10)
    elif node_type == 'num':
        label = f"{node_data['value']}"
        node_class = 'num-node'
        node_width = max(50, len(label) * 10)
    elif node_type == 'op':
        label = f"{node_data['value']}"
        node_class = 'op-node'
        node_width = max(50, len(label) * 10)
    else:
        label = node_type
        node_class = 'default-node'
        node_width = max(50, len(label) * 10)
    
    node_widths[node_id] = node_width
    
    if y not in level_positions:
        level_positions[y] = []
    
    original_x = x
    
    # calculate minimum space needed between nodes to avoid visual overlap
    min_separation = node_width / 2 + 40
    
    level_positions[y].sort()
    
    # check if current position would cause overlap
    overlap_detected = False
    for pos_node_id, pos_x in level_positions[y]:
        if abs(pos_x - x) < (min_separation + node_widths.get(pos_node_id, 40) / 2):
            overlap_detected = True
            break
    
    # resolve node overlap by trying different positions
    if overlap_detected:
        shift_right = x
        shift_left = x
        shift_amount = min_separation
        max_attempts = 10
        attempts = 0
        
        while overlap_detected and attempts < max_attempts:
            shift_right += shift_amount
            overlap_right = False
            for pos_node_id, pos_x in level_positions[y]:
                if abs(pos_x - shift_right) < (min_separation + node_widths.get(pos_node_id, 40) / 2):
                    overlap_right = True
                    break
            
            shift_left -= shift_amount
            overlap_left = False
            for pos_node_id, pos_x in level_positions[y]:
                if abs(pos_x - shift_left) < (min_separation + node_widths.get(pos_node_id, 40) / 2):
                    overlap_left = True
                    break
            
            # use whichever direction has no overlap
            if not overlap_right:
                x = shift_right
                overlap_detected = False
            elif not overlap_left:
                x = shift_left
                overlap_detected = False
            
            shift_amount += 20
            attempts += 1
        
        # if horizontal shifts don't work, create a new vertical level
        if overlap_detected:
            new_y = y + y_offset / 2
            while new_y in level_positions:
                new_y += y_offset / 4
            
            y = new_y
            level_positions[y] = []
            overlap_detected = False
    
    level_positions[y].append((node_id, x))
    
    children = node_data.get('children', [])
    tree_depth = get_max_depth(node_data)
    
    # reduce horizontal spread for deep trees to keep visualization compact
    if tree_depth > 4:
        x_offset = max(60, 120 - (tree_depth * 10))
    
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
    
    if parent_id:
        elements.append({
            'data': {
                'source': parent_id,
                'target': node_id,
                'id': f'edge_{parent_id}_{node_id}'
            }
        })
    
    child_count = len(children)
    
    # position nodes based on number of children
    if child_count == 2:
        # left child
        json_to_cytoscape_elements(
            children[0], 
            node_id, 
            elements, 
            level + 1, 
            x - x_offset,
            y + y_offset,
            x_offset,
            y_offset,
            level_positions,
            node_widths
        )
        
        # right child
        json_to_cytoscape_elements(
            children[1], 
            node_id, 
            elements, 
            level + 1, 
            x + x_offset,
            y + y_offset,
            x_offset,
            y_offset,
            level_positions,
            node_widths
        )
    elif child_count == 1:
        # single child positioned directly below
        json_to_cytoscape_elements(
            children[0], 
            node_id, 
            elements, 
            level + 1, 
            x,
            y + y_offset,
            x_offset,
            y_offset,
            level_positions,
            node_widths
        )
    
    return elements

# Helper function to determine tree depth
def get_max_depth(node):
    """calculate the maximum depth of a tree"""
    if not node.get('children'):
        return 1
    
    max_child_depth = 0
    for child in node.get('children', []):
        child_depth = get_max_depth(child)
        max_child_depth = max(max_child_depth, child_depth)
    
    return 1 + max_child_depth

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
            layout={'name': 'preset'},  # preset layout for fixed positions
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
    
    elements = []
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