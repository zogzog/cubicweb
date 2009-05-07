

Implementation
--------------
BNF grammar
~~~~~~~~~~~

The terminal elements are in capital letters, non-terminal in lowercase.
The value of the terminal elements (between quotes) is a Python regular
expression.
::

     statement:: = (select | delete | insert | update) ';'


     # select specific rules
     select      ::= 'DISTINCT'? E_TYPE selected_terms restriction? group? sort?

     selected_terms ::= expression ( ',' expression)*

     group       ::= 'GROUPBY' VARIABLE ( ',' VARIABLE)*

     sort        ::= 'ORDERBY' sort_term ( ',' sort_term)*

     sort_term   ::=  VARIABLE sort_method =?

     sort_method ::= 'ASC' | 'DESC'


     # delete specific rules
     delete ::= 'DELETE' (variables_declaration | relations_declaration) restriction?


     # insert specific rules
     insert ::= 'INSERT' variables_declaration ( ':' relations_declaration)? restriction?


     # update specific rules
     update ::= 'SET' relations_declaration restriction


     # common rules
     variables_declaration ::= E_TYPE VARIABLE (',' E_TYPE VARIABLE)*

     relations_declaration ::= simple_relation (',' simple_relation)*

     simple_relation ::= VARIABLE R_TYPE expression

     restriction ::= 'WHERE' relations

     relations   ::= relation (LOGIC_OP relation)*
                   | '(' relations')'

     relation    ::= 'NOT'? VARIABLE R_TYPE COMP_OP? expression
                   | 'NOT'? R_TYPE VARIABLE 'IN' '(' expression (',' expression)* ')'
                   
     expression  ::= var_or_func_or_const (MATH_OP var_or_func_or_const) *
                   | '(' expression ')'

     var_or_func_or_const ::= VARIABLE | function | constant

     function    ::= FUNCTION '(' expression ( ',' expression) * ')'

     constant    ::= KEYWORD | STRING | FLOAT | INT

     # tokens
     LOGIC_OP ::= ',' | 'OR' | 'AND'
     MATH_OP  ::= '+' | '-' | '/' | '*'
     COMP_OP  ::= '>' | '>=' | '=' | '<=' | '<' | '~=' | 'LIKE'

     FUNCTION ::= 'MIN' | 'MAX' | 'SUM' | 'AVG' | 'COUNT' | 'UPPER' | 'LOWER'

     VARIABLE ::= '[A-Z][A-Z0-9]*'
     E_TYPE   ::= '[A-Z]\w*'
     R_TYPE   ::= '[a-z_]+'

     KEYWORD  ::= 'TRUE' | 'FALSE' | 'NULL' | 'TODAY' | 'NOW'
     STRING   ::= "'([^'\]|\\.)*'" |'"([^\"]|\\.)*\"'
     FLOAT    ::= '\d+\.\d*'
     INT      ::= '\d+'


Internal representation (syntactic tree)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The tree research does not contain the selected variables 
(e.g. there is only what follows "WHERE").

The insertion tree does not contain the variables inserted or relations
defined on these variables (e.g. there is only what follows "WHERE").

The removal tree does not contain the deleted variables and relations
(e.g. there is only what follows the "WHERE").

The update tree does not contain the variables and relations updated
(e.g. there is only what follows the "WHERE").

::

     Select         ((Relationship | And | Or)?, Group?, Sort?)
     Insert         (Relations | And | Or)?
     Delete         (Relationship | And | Or)?
     Update         (Relations | And | Or)?

     And            ((Relationship | And | Or), (Relationship | And | Or))
     Or             ((Relationship | And | Or), (Relationship | And | Or))

     Relationship   ((VariableRef, Comparison))

     Comparison     ((Function | MathExpression | Keyword | Constant | VariableRef) +)

     Function       (())
     MathExpression ((MathExpression | Keyword | Constant | VariableRef), (MathExpression | Keyword | Constant | VariableRef))

     Group          (VariableRef +)
     Sort           (SortTerm +)
     SortTerm       (VariableRef +)

     VariableRef    ()
     Variable       ()
     Keyword        ()
     Constant       ()


Known limitations
~~~~~~~~~~~~~~~~~

- The current implementation does not support linking two relations of type 'is'
  with a OR. I do not think that the negation is supported on this type of
  relation (XXX FIXME to be confirmed).

- Relations defining the variables must be left to those using them.  For
  example::

     Point P where P abs X, P ord Y, P value X+Y

  is valid, but::

     Point P where P abs X, P value X+Y, P ord Y

  is not.

- missing proper explicit type conversion,  COALESCE and certainly other things...

- writing a rql query require knowledge of the schema used (with real relation
  names and entities, not those viewing in the user interface). On the other
  hand, we can not really bypass that, and it is the job of a user interface to
  hide the RQL.


Topics
~~~~~~

It would be convenient to express the schema matching
relations (non-recursive rules)::

     Document class Type <-> Document occurence_of Fiche class Type
     Sheet class Type    <-> Form collection Collection class Type
    
Therefore 1. becomes::

     Document X where
     X class C, C name 'Cartoon'
     X owned_by U, U login 'syt'
     X available true

I'm not sure that we should handle this at RQL level ...

There should also be a special relation 'anonymous'.
