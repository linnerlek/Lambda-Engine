from dash import Dash, html, dcc, callback, Output, Input, State, ctx
import plotly.express as px
import plotly.graph_objects as go
import igraph as ig
import networkx as nx
from argparse import ArgumentParser
from furl import furl

from Lambda import get_initial_tree
from Lambda import get_next_tree
from Lambda import get_next_tree_after_math
from Lambda import tree2dict, to_string, json2tree

def build_tree(G, node_data, parent=None):
    # create a new node
    node_id = node_data['nodeid']
    G.add_node(node_id, 
               type=node_data['type'], 
               beta=node_data.get('beta'), 
               var=node_data.get('var'), 
               value=node_data.get('value'))
    if parent is not None:
        G.add_edge(parent, node_id)
    # add the node's children recursively
    for child_data in node_data['children']:
        build_tree(G, child_data, node_id)

def draw_graph(G):
    g = ig.Graph()
    g = g.from_networkx(G)
    color_map = {'NO':'red', 'YES':'green', None:'lightgray'}
    node_map = {'lambda': 5, 'apply': 2, 'name':3, 'op': 4, 'num':5}

    vdf = g.get_vertex_dataframe()

    #layout_ = g.layout('rt') #Reingold-Tilford layout, seems like this is the only one working for trees
    layout_ = g.layout_reingold_tilford(root=[0])
    edge_x = []
    edge_y = []
    for edge in g.get_edgelist():
        x0, y0 = layout_[edge[0]]
        x1, y1 = layout_[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    texts = []
    for node in G.nodes():
        texts.append(node+":"+G.nodes[node]["type"]+":"+str(G.nodes[node]["beta"]))
    #print(texts)

    node_x = [pos[0] for pos in layout_]
    node_y = [pos[1] for pos in layout_]

    symbols = []
    for idx, row in vdf.iterrows():
        if row['type'] == 'lambda':
            symbols.append('triangle-up')
        elif row['type'] == 'apply':
            symbols.append('circle')
        else:
            symbols.append('square')

    node_trace = go.Scatter(x=node_x, 
                            y=node_y, 
                            mode='markers', 
                            marker=dict(size=30, color=[color_map[t] for t in g.vs['beta']], symbol=symbols),
                            hovertemplate='', hoverinfo='none')
    node_trace.customdata = texts
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(width=2, color='black'),
                            hovertemplate='', hoverinfo='none')
    layout = go.Layout(showlegend=False, hovermode='closest', margin=dict(b=20,l=5,r=5,t=40))
    fig = go.Figure(data=[edge_trace, node_trace], layout=layout)
    for node in G.nodes():
        x, y = layout_[vdf[vdf._nx_name==node].index.values.item()]
        prop = G.nodes[node]
        if prop['type'] in ['name', 'op', 'num']:
            fig.add_annotation(
                x=x, y=y,
                text=prop['value'],
                xshift=0, yshift=0, align='center', showarrow=False,
            )
        elif prop['type'] =='lambda':
            fig.add_annotation(
                x=x, y=y,
                text=f'{prop["var"]}',
                xshift=0, yshift=0, align='center', showarrow=False,
            )
        else:
            fig.add_annotation(
                x=x, y=y,
                text=f'{node}',
                xshift=0, yshift=0, align='center', showarrow=False, visible=False,
            )

    fig.update_layout(yaxis = dict(autorange="reversed", showgrid=False, zeroline=False, showticklabels=False),
                      xaxis = dict(showgrid=False, zeroline=False, showticklabels=False))
    return fig

def blank_fig():
    fig = go.Figure(go.Scatter(x=[], y = []))
    fig.update_layout(template = None)
    fig.update_xaxes(showgrid = False, showticklabels = False, zeroline=False)
    fig.update_yaxes(showgrid = False, showticklabels = False, zeroline=False)
    return fig

app = Dash(__name__)

app.layout = html.Div(children=[
    dcc.Store(id='tree'),
    dcc.Store(id='prevtrees'),
    dcc.Location(id='url'),
    html.H2(children='Lambda Engine', style={'textAlign': 'center'}),
    html.Div(children=[
        html.Button('Back', id='back', style={'marginRight': '10px'}),
        dcc.Input(id='lambdaex', type='text', value='', placeholder='Enter an expression...', style={'marginRight': '10px'}),
        html.Button('Submit', id='submit', style={'marginRight': '10px'}),
        html.Button('Reset', id='reset'),
        dcc.ConfirmDialog( id='parseerror', message='Parse Error!',),
        #dcc.Alert( id="alert", message="This is an alert!", dismissible=True,),
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'marginBottom': '20px'}),
    html.Div(children=[
        dcc.Graph(id='graph-content', style={'width': '60%'}, figure=blank_fig()),
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
    html.Div(children=[
        html.P(id='stringtree'),
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
    ], style={'maxWidth': '1000px', 'margin': '0 auto'})

@callback(Output('tree', 'data', allow_duplicate=True),
          Output('prevtrees', 'data', allow_duplicate=True),
          Output('submit', 'disabled'),
          Output("parseerror", "displayed"),
          Input('submit', 'n_clicks'), 
          State('lambdaex', 'value'),
          prevent_initial_call=True)
def submit_initial_expression(n_clicks, value):
    tree = get_initial_tree(value)
    if tree["status"] == "OK":
        return tree, [tree], True, False
    else:
        print("ERROR parsing lambda expression",tree["message"])
        return None,None,False,True
    
@callback(Output('tree', 'data', allow_duplicate=True),
          Output('prevtrees', 'data', allow_duplicate=True),
          Output('submit', 'disabled',allow_duplicate=True),
          Output("parseerror", "displayed", allow_duplicate=True),
          Input('url', 'href'), 
          prevent_initial_call=True)
def submit_initial_expression_url(href):
    f = furl(href)
    expression = f.args['expression']
    expression = str(expression).replace('%20', ' ')
    tree = get_initial_tree(expression)
    if tree["status"] == "OK":
        print(tree)
        return tree, [tree], True, False
    else:
        print("ERROR parsing lambda expression",tree["message"])
        return None, None, False, True

@callback(Output('graph-content', 'figure'), 
          Output('stringtree', 'children'), 
          Input('tree', 'data'),
          prevent_initial_call=True)
def retrieve_data_from_store(tree):
    G = nx.DiGraph()
    # build the tree from the JSON data
    if tree == None:
        return blank_fig(), ""
    root_data = tree['expr_tree_json']
    build_tree(G, root_data)
    fig = draw_graph(G)
    stringtree = ''
    if type(tree) == dict:
        stringtree = json2tree(tree['expr_tree_json'])
    return fig, to_string(stringtree)

@callback(Output('tree', 'data', allow_duplicate=True),
          Output('prevtrees', 'data', allow_duplicate=True),
          Output('graph-content', 'clickData'), 
          Input('graph-content', 'clickData'), 
          State('tree', 'data'),
          State('prevtrees', 'data'),
          prevent_initial_call=True)
def select_node(selection, tree, prevtrees):
    if tree == None or "customdata" not in selection["points"][0]:
        return
    selected_node_id,selected_node_type, selected_node_beta = selection["points"][0]["customdata"].split(":")
    if selected_node_type == 'apply' and selected_node_beta == "YES":
        tree = get_next_tree(tree['expr_tree_json'], selected_node_id)
        tree = tree2dict(tree)
        tree = {"status": "OK", "expr_tree_json": tree}
        if prevtrees is []:
            prevtrees = [tree]
        else:
            prevtrees.append(tree)
        return tree, prevtrees, None
    elif selected_node_type == 'op':
        tree = get_next_tree_after_math(tree['expr_tree_json'], selected_node_id)
        tree = tree2dict(tree)
        tree = {"status": "OK", "expr_tree_json": tree}
        if prevtrees is []:
            prevtrees = [tree]
        else:
            prevtrees.append(tree)
        return tree, prevtrees, None
    else:
        return

@callback(Output('tree', 'data', allow_duplicate=True),
          Output('prevtrees', 'data', allow_duplicate=True),
          Input('back', 'n_clicks'), 
          State('tree', 'data'),
          State('prevtrees', 'data'),
          prevent_initial_call=True)
def go_back(n_clicks, tree, prevtrees):
    if len(prevtrees) > 1:
        pt = prevtrees.pop(-1) #take the last tree from the store
        return prevtrees[-1], prevtrees

@app.callback(Output('back', 'disabled'),
              Input('prevtrees', 'data'),
              prevent_initial_call=True)
def set_back_button_disabled_state(prevtrees):
    if prevtrees != None:
        return len(prevtrees) == 1
    else:
        return False
    
@app.callback(Output('prevtrees', 'data', allow_duplicate=True),
              Output('tree', 'data', allow_duplicate=True),
              Output('back', 'disabled', allow_duplicate=True),
              Output('lambdaex', 'value', allow_duplicate=True),
              Output('submit', 'disabled', allow_duplicate=True),
              Input('reset', 'n_clicks'),  prevent_initial_call=True)
def reset(n_clicks):
    return [], None, True, '', False

if __name__ == '__main__':
    parser = ArgumentParser(prog='Lambda Engine',
                            description='Process Lambda calculus and provides a graphical view of the steps of the process'
                            )
    parser.add_argument('--hostname', default='localhost')
    parser.add_argument('--port', default='8081')
    args = parser.parse_args()

    app.run_server(debug=False, host=args.hostname, port=args.port)
