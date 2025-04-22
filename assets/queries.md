# **Lambda Engine – Examples**

This panel contains a set of example lambda expressions you can click to auto-fill the input field. Try them out to see how beta-reduction and evaluation works!

---

## Examples

### Example 1: Simple addition using nested lambdas
```
(((lambda x (lambda y (+ x y))) 10) 5);
```
- Defines a function that adds two numbers and applies it to `10` and `5`
- Try clicking through "apply" nodes and then the `+` operator

### Example 2: Function application with square function
```
(((lambda f (lambda x (f x))) (lambda y (* y y))) 12);
```
- Applies a squaring function `f` to the value `12`

### Example 3: Church-style double application
```
((((lambda f (lambda x ((f x) f))) (lambda y (lambda g (g (* y y))))) 2) (lambda a a));
```
- Advanced structure involving nested applications
- Shows multiple levels of beta-reduction

### Example 4: Y combinator
```
(lambda f ((lambda x (f (x x)))(lambda x (f (x x)))));
```
- Demonstrates the Y combinator pattern
- Useful in recursion and higher-order functions

---

## How to Use
- **Click any expression above** to insert it into the text box
- Then press **Submit** to generate its expression tree
- Explore the tree by clicking on green `apply` nodes or arithmetic operators to reduce step by step

💡 Try combining your own lambda expressions with arithmetic to create custom examples!
