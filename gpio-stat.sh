#!/bin/sh
	#clear ;
echo "\033[0m--- " `date` " ---" ;
echo "\033[0mReleu traf:" `gpio -g read 18` ;
echo "\033[0mReleu 1:" `gpio -g read 21` ;
echo "\033[0mReleu 2:" `gpio -g read 20` ;
echo "\033[0mReleu 3:" `gpio -g read 16` ;
echo "\033[0mReleu 4:" `gpio -g read 12` ;
echo "\033[0;94mSenzor ploaie:" `gpio -g read 23` ;
echo "\033[0;31mLED rosu:" `gpio -g read 19` ;
echo "\033[0;32mLED verde:" `gpio -g read 13` ;
echo "\033[0;36mLED albastru: " `gpio -g read 26` ;
echo "\033[0;44mButon 1:" `gpio -g read 9` ;
echo "\033[0;44mButon 2:" `gpio -g read 11` ;
echo "\033[0;44mButon 3:" `gpio -g read 22` ;
echo "\033[0;44mButon 4:" `gpio -g read 10` ;
echo "\033[0m" ;

