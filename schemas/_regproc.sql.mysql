/* -*- sql -*- 

   mysql specific registered procedures, 

*/

/* XXX limit_size version dealing with format as postgres version does.
   XXX mysql doesn't support overloading, each function should have a different name
       
   NOTE: fulltext renamed since it cause a mysql name conflict
 */

CREATE FUNCTION text_limit_size(vfulltext TEXT, maxsize INT)
RETURNS TEXT
NO SQL
BEGIN
    IF LENGTH(vfulltext) < maxsize THEN
       RETURN vfulltext;
    ELSE
       RETURN SUBSTRING(vfulltext from 1 for maxsize) || '...';
    END IF;
END ;;
