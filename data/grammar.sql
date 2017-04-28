# These are comments. Ignore them while processing this file

{QUESTION} => what
{SUM} => sum | total
{POSS} => and
{SMALL} => smallest | lowest
{BIG} => largest | biggest


# Here are the templates

# Single column
{QUESTION} the total number of {ENT1} 	 how many {ENT1} are there? 	 SELECT count(1) FROM {ENT1}
{QUESTION} all the {ENT1} {ENT1}.{DEF} 	 SELECT {ENT1}.{DEF} FROM {ENT1}
{QUESTION} the {ENT1}.{COL1} of all {ENT1} 	 {QUESTION} all {ENT1} {ENT1}.{COL1} 	 SELECT {ENT1}.{COL1} FROM {ENT1}
{QUESTION} the {SUM} of {ENT1} {ENT1}.{COL1} 	 {QUESTION} the combined {ENT1}.{COL1} of {ENT1} 	 SELECT sum({ENT1}.{COL1}) FROM {ENT1}
{QUESTION} the average of {ENT1} {ENT1}.{COL1} 	 SELECT avg({ENT1}.{COL1}) FROM {ENT1}
{QUESTION} all {ENT1} whose {ENT1}.{COL1} is {ENT1}.{COL1}.{LITERAL} {ENT1}.{DEF} 	 {QUESTION} all {ENT1} having {ENT1}.{COL1} {ENT1}.{COL1}.{LITERAL} {ENT1}.{DEF} 	 {ENT1}.{COL1}.{LITERAL} {ENT1} {ENT1}.{DEF} 	 SELECT {ENT1}.{DEF} FROM {ENT1} WHERE {ENT1}.{COL1} = {ENT1}.{COL1}.{LITERAL}
{QUESTION} the {ENT1}.{COL1} of {ENT1}.{COL2}.{LITERAL} 	 SELECT {ENT1}.{COL1} FROM {ENT1}  WHERE {ENT1}.{COL2} = {ENT1}.{COL2}.{LITERAL}

{QUESTION} the {BIG} of {ENT1} {ENT1}.{COL1} 	 SELECT max({ENT1}.{COL1}) FROM {ENT1}
{QUESTION} the {SMALL} of {ENT1} {ENT1}.{COL1} 	 SELECT min({ENT1}.{COL1}) FROM {ENT1}
{QUESTION} the {SUM} {ENT1}.{COL1} of {ENT1}.{COL2}.{LITERAL} 	 SELECT sum({ENT1}.{COL1}) FROM {ENT1}  WHERE {ENT1}.{COL2} = {ENT1}.{COL2}.{LITERAL}
{QUESTION} the average {ENT1}.{COL1} of {ENT1}.{COL2}.{LITERAL} 	 SELECT avg({ENT1}.{COL1}) FROM {ENT1}  WHERE {ENT1}.{COL2} = {ENT1}.{COL2}.{LITERAL}
{QUESTION} the {MAX} {ENT1}.{COL1} of {ENT1}.{COL2}.{LITERAL} 	 SELECT max({ENT1}.{COL1}) FROM {ENT1}  WHERE {ENT1}.{COL2} = {ENT1}.{COL2}.{LITERAL}
{QUESTION} the {MIN} {ENT1}.{COL1} of {ENT1}.{COL2}.{LITERAL} 	 SELECT min({ENT1}.{COL1}) FROM {ENT1}  WHERE {ENT1}.{COL2} = {ENT1}.{COL2}.{LITERAL}
{QUESTION} the total number of {ENT1} in {ENT1}.{COL1}.{LITERAL} 	 how many {ENT1} are there in {ENT1}.{COL1}.{LITERAL} ? 	 SELECT count(1) FROM {ENT1} WHERE {ENT1}.{COL1} = {ENT1}.{COL1}.{LITERAL}


# Example: Get me all Authors and Organizations
{QUESTION} all {ENT1} {POSS} {ENT2} {ENT1}.{DEF} {ENT2}.{DEF} 	 SELECT {ENT1}.{DEF} , {ENT2}.{DEF} FROM JOIN_FROM({ENT1}, {ENT2}) WHERE JOIN_WHERE({ENT1}, {ENT2})

# Example: Get me all Authors in Europe
{QUESTION} all {ENT1} in {ENT2}.{COL1}.{LITERAL} {ENT1}.{DEF} 	 {ENT1} {ENT2}.{COL1}.{LITERAL} {ENT1}.{DEF} 	 SELECT {ENT1}.{DEF} FROM JOIN_FROM({ENT1}, {ENT2}) WHERE JOIN_WHERE({ENT1}, {ENT2}) AND {ENT2}.{COL1} = {ENT2}.{COL1}.{LITERAL}

# Same as above but explicity specify the second table
{QUESTION} all {ENT1} having {ENT2}.{COL1} as {ENT2}.{COL1}.{LITERAL} {ENT1}.{DEF} 	 SELECT {ENT1}.{DEF} FROM JOIN_FROM({ENT1}, {ENT2}) WHERE JOIN_WHERE({ENT1}, {ENT2}) AND {ENT2}.{COL1} = {ENT2}.{COL1}.{LITERAL}

# Superlatives
{QUESTION} the {SMALL} {ENT1} {ENT1}.{COL1} 	 SELECT min({ENT1}.{COL1}) FROM {ENT1}
{QUESTION} the {BIG} {ENT2} {ENT1}.{COL1} 	 SELECT max({ENT1}.{COL1}) FROM {ENT1}
{QUESTION} the {ENT1} with the {BIG} {ENT1}.{COL1} {ENT1}.{DEF} 	 SELECT {ENT1}.{DEF} FROM {ENT1} WHERE {ENT1}.{COL1} = ( SELECT max({ENT1}.{COL1}) FROM {ENT1} )

# Two entities
{ENT1}.{COL1}.{LITERAL} {ENT2}.{COL1}.{LITERAL} {ENT2} {ENT1}.{DEF} {ENT2}.{DEF} 	 SELECT {ENT1}.{DEF} , {ENT2}.{DEF} FROM JOIN_FROM({ENT1}, {ENT2}) WHERE JOIN_WHERE({ENT1}, {ENT2}) AND {ENT2}.{COL1} = {ENT2}.{COL1}.{LITERAL} AND {ENT1}.{COL1} = {ENT1}.{COL1}.{LITERAL}
{QUESTION} the total number of {ENT1} of {ENT2}.{COL1}.{LITERAL} 	 how many {ENT1} are there in {ENT2}.{COL1}.{LITERAL} ? 	 SELECT count(1) FROM JOIN_FROM({ENT1}, {ENT2}) WHERE JOIN_WHERE({ENT1}, {ENT2}) AND {ENT2}.{COL1} = {ENT2}.{COL1}.{LITERAL}
