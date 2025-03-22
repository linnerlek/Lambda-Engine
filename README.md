# Lambda Calculus Visualizer

This application is a `Dash`-based tool for visualizing and evaluating lambda calculus expressions. It features an interactive tree view rendered with `dash-cytoscape`, allowing users to perform beta reductions and arithmetic operations step-by-step.

---

## Installation

- Ensure you have:
  - **Python 3.11+**

- Clone the repository:

  ```bash
  git clone https://github.com/linnerlek/Lambda-Engine.git
  cd Lambda-Engine/
  ```

- Install dependencies:

  ```bash
  pip3 install -r requirements.txt
  ```

- Start the application with:

  ```bash
  python app.py --hostname <hostname> --port <port>
  ```
    - If you do not specify the hostname and port by default localhost and 8081 will be used

---

## Usage
1. Enter a lambda expression in the input box
2. Click "Submit" to visualize the expression tree
3. Interact with the tree:
    - Green nodes: click to perform beta reduction
    - Operator nodes: click to evaluate arithmetic
4. Use "Back" to return to previous states
5. Use "Reset" to start over

---

## Expression Format
### Node types
- Lambda abstractions: triangles
- Applications: circles (green when reducible)
- Variables/numbers: rectangles

### Grammar
A lambda expression is defined inductively as follows:

- A variable is a lambda expression (e.g. x, y, m, n, etc)
- A number is a lambda expression (e.g. 10, 2, -5, 6.5, etc)
- If M is a lambda expression and x is a variable, then (lambda x M) - is a lambda expression
- If M and N are lambda expressions then (M N) is a lambda expression
- If M and N are lambda expressions then (op M N) is a lambda expression, where op is +, -, *, or /

### Examples
```
(((lambda x (lambda y (+ x y))) 10) 5);
```
```
(((lambda f (lambda x (f x))) (lambda y (* y y))) 12);
```
```
((((lambda f (lambda x ((f x) f))) (lambda y (lambda g (g (* y y))))) 2) (lambda a a));
```
```
(lambda f ((lambda x (f (x x)))(lambda x (f (x x)))));
```

**Note:** Terminate all expressions with a semicolon (`;`).