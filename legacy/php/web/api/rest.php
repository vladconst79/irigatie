<?php
header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("Cache-Control: post-check=0, pre-check=0", false);
header("Pragma: no-cache");

function get_serial() {
    $cpuserial = "0000000000000000";
    try {
        $file = file("/proc/cpuinfo");
        foreach ($file as $key => $value) {
            if (substr($value, 0, 6) == "Serial") {
                $cpuserial = substr($value, 10, 16);
            }
        }
    } catch (Exception $e) {
        syslog(LOG_ERR, "Exception :: " . $e->getMessage());
        $cpuserial = "ERROR000000000";
    }
    return $cpuserial;
}

function encodeHtml($responseData) {
    $htmlResponse = "<table border='1'>";
    foreach ($responseData as $key=>$row) {
        if ($key == 0) {
            $htmlResponse .= "<thead><tr>";
            foreach ($row as $key2=>$row2) {
                $htmlResponse .= "<th>" . $key2 . "</th>";
            }
            $htmlResponse .= "</thead>";
        }
        $htmlResponse .= "<tr>";
        foreach ($row as $key2=>$row2) {
            $htmlResponse .= "<td>" . $row2 . "</td>";
        }
        $htmlResponse .= "</tr>";
    }
    $htmlResponse .= "</table>";
    return $htmlResponse;
}

function encodeJson($responseData) {
    $jsonResponse = json_encode($responseData);
    return $jsonResponse;
}

function encodeXML($array, $rootElement = null, $xml = null) {
    $_xml = $xml;
    // If there is no Root Element then insert root
    if ($_xml === null) {
        $_xml = new SimpleXMLElement($rootElement !== null ? $rootElement : '<root/>');
    }
    // Visit all key value pair
    foreach ($array as $k => $v) {
        // If there is nested array then
        if (is_array($v)) {
            // Call function for nested array
            encodeXML($v, $k, $_xml->addChild($k));
        }
        else {
            // Simply add child element.
            $_xml->addChild($k, $v);
        }
    }
    return $_xml->asXML();
}

$ini_array = parse_ini_file("../irigatie.ini");
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);

syslog(LOG_INFO, basename($_SERVER['REQUEST_URI']) . " :: " . print_r($_REQUEST, true) . " :: " . $_SERVER['REQUEST_METHOD']);
syslog(LOG_INFO, basename($_SERVER['REQUEST_URI']) . " :: " . file_get_contents("php://input"));
if (isset($_POST["op"])) {
    $op = $_POST["op"];
}
switch ($op) {
    case "select":
        if (isset($_POST["tabela"])) {
            $tabela = $_POST["tabela"];
            $sql = "SELECT * FROM {$tabela}";
            if (isset($_POST["criteriu"])) {
                $criteriu = $_POST["criteriu"];
                $sql .= " WHERE {$criteriu}";
            }
            if (isset($_POST["limita"])) {
                $limita = (int)$_POST["limita"];
                $sql .= " LIMIT {$limita}";
            }
            if (isset($_POST["ordine"])) {
                $sql .= " ORDER BY {$_POST['ordine']} ASC";
            }
            $sql .= ";";
        }
        break;
    case "view":

        break;
    case "update":

        break;
    case "execute":

        break;
    case "stop":

        break;
    case "insert":

        break;
    case "delete":

        break;
    case "search":

        break;
}
if (!isset($simulation) || !$simulation) {
    if (isset($sql)) {
        if (isset($multi) && $multi) {
            $result = mysqli_multi_query($conn, $sql);
        } else {
            $result = mysqli_query($conn, $sql);
        }
        $raw_data = mysqli_fetch_all($result, MYSQLI_ASSOC);
        if (isset($postsql)) {
            $result_last_id = mysqli_query($conn, "SELECT LAST_INSERT_ID() AS id;");
            $raw_last_id = mysqli_fetch_row($result_last_id);
            $pacientid = $raw_last_id[0];
            $postsql = str_replace("#missingid#", $pacientid, $postsql);
//            syslog(LOG_DEBUG, "Query final INSERT :: " . $postsql);
            mysqli_query($conn, $postsql);
            mysqli_free_result($result_last_id);
        }
        if (isset($get_last_id) && $get_last_id) {
            $result_last_id = mysqli_query($conn, "SELECT LAST_INSERT_ID() AS id;");
            $raw_data = mysqli_fetch_all($result_last_id, MYSQLI_ASSOC);
        }
        $requestContentType = $_SERVER['HTTP_ACCEPT'];
        if (strpos($requestContentType, 'application/json') !== false) {
            header('Content-Type: application/json');
            $response = encodeJson($raw_data);
            if ($response == "null") {
                $response = '[{"Rezultat":"OK!"}]';
            }
        } elseif (strpos($requestContentType, 'application/xml') !== false) {
            header('Content-Type: application/xml');
            $response = encodeXml($raw_data);
        } else if (strpos($requestContentType, 'text/html') !== false) {
            header('Content-Type: text/html');
            $response = encodeHtml($raw_data);
        } else {
            $response = "Unknown request type";
        }
        echo $response;
        mysqli_free_result($result);
    }
}
mysqli_close($conn);