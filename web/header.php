<?php
session_set_cookie_params(28800,"/");
session_start();
header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("Cache-Control: post-check=0, pre-check=0", false);
header("Pragma: no-cache");
include('functions.php');
$ini_array = parse_ini_file("irigatie.ini");
?>

<!DOCTYPE HTML>
<html lang="en-US">
<head>
    <meta charset="UTF-8">
    <title>Programator irigiatie</title>
    <link rel="stylesheet" href="css/bootstrap.css" />
    <link rel="stylesheet" href="css/styles.css" />
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>
    <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"></script>
</head>
<body>
<div id="head" style="max-width: 1680px">
    <div class="row">
        <div class="col">
            <img src="images/header-irigatii.jpg" width="1640">
        </div>
    </div>
    <div style="height: 20px"></div>
    <div class="row">
        <div class="col-md-2">
            <a href="mainpage.php"><?php greenbutton("Programe");?></a>
        </div>
        <div class="col-md-2">
            <a href="run.php"><?php greenbutton("Manual")?></a>
        </div>
        <div class="col-md-2">
            <a href="trasee.php"><?php greenbutton("Trasee")?></a>
        </div>
        <div class="col-md-2">
            <a href="users.php"><?php greenbutton("Useri")?></a>
        </div>
    </div>
</div>
</body>

