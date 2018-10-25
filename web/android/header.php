<?php
session_set_cookie_params(28800,"/");
session_start();
header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("Cache-Control: post-check=0, pre-check=0", false);
header("Pragma: no-cache");
$ini_array = parse_ini_file("../irigatie.ini");