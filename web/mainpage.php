<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    die("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_connect_error()."}</pre>");
}
?>
<div class="container" id="tables" style="margin-left: 20px">
    <form action="mainpage.php" method="POST" id="myForm" onsubmit="window.location.reload()">
        <div class="form-group row">
            <table class="table table-hover" id="myTable" style="white-space: nowrap">
                <thead>
                <tr>
                    <th style="vertical-align: center; horiz-align: center">ID</th>
                    <th style="vertical-align: center">TRASEU</th>
                    <th style="vertical-align: center">ORA</th>
                    <th style="vertical-align: center">MINUTUL</th>
                    <th style="vertical-align: center">ZIUA LUNII</th>
                    <th style="vertical-align: center">LUNA</th>
                    <th style="vertical-align: center">ZIUA SAPTAMANII</th>
                    <th style="vertical-align: center">DURATA</th>
                    <th style="vertical-align: center" title="1 l/mp ≈ 4">PLOAIE</th>
                    <th style="vertical-align: center">PRECIPITATII</th>
                    <th></th><th></th>
                </tr>
                </thead>
                <?php
                $sql = "SELECT trasee.denumire, trasee.id AS tid, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id;";
                $result = mysqli_query($conn, $sql);
                while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
                    if (isset($_POST['edit']) && ($_POST['edit'] == $row['id'])) {
                        $sql = "SELECT id, denumire FROM trasee;";
                        $tresult = mysqli_query($conn, $sql);
                        echo "<tr>";
                        echo "<td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0' type='submit' name='edit' value='".$row['id']."' class='btn btn-default' disabled>".$row['id']."</button></td>";
                        echo "<td><select name='traseu' class='form-control'>";
                        while ($trow = mysqli_fetch_array($tresult, MYSQLI_ASSOC)) {
                            if ($trow['id'] == $row['tid']){
                                echo "<option value='".$trow['id']."' selected>".$trow['denumire']."</option>";
                            } else {
                                echo "<option value='" . $trow['id'] . "'>" . $trow['denumire'] . "</option>";
                            }
                        }
                        echo "</select></td>";
                        echo "<td><input type='text' name='h' class='form-control' value='".$row['h']."' style='width: min-content'></td>";
                        echo "<td><input type='text' name='m' class='form-control' value='".$row['m']."' style='width: min-content'></td>";
                        echo "<td><input type='text' name='dom' class='form-control' value='".$row['dom']."' style='width: min-content'></td>";
                        echo "<td><input type='text' name='mon' class='form-control' value='".$row['mon']."' style='width: min-content'></td>";
                        echo "<td><input type='text' name='dow' class='form-control' value='".$row['dow']."' style='width: min-content'></td>";
                        echo "<td><input type='number' name='durata' class='form-control' value='".$row['durata']."'></td>";
                        echo "<td><input type='number' name='max_ploaie' class='form-control' title='1 l/mp ≈ 4' value='".$row['max_ploaie']."'></td>";
                        echo "<td style='vertical-align: center'>".$row['ploaie']."</td>";
                        echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='edex' value='".$row['id']."' class='btn btn-success'>Confirma</button></td>";
                        echo "</tr>";
                        mysqli_free_result($tresult);
                    } else {
                        echo "<tr>";
                        echo "<td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0' type='submit' name='edit' value='".$row['id']."' class='btn btn-default'>".$row['id']."</button></td>";
                        echo "<td style='vertical-align: center'>".$row['denumire']."</td>";
                        echo "<td style='vertical-align: center'>".$row['h']."</td>";
                        echo "<td style='vertical-align: center'>".$row['m']."</td>";
                        echo "<td style='vertical-align: center'>".$row['dom']."</td>";
                        echo "<td style='vertical-align: center'>".$row['mon']."</td>";
                        echo "<td style='vertical-align: center'>".$row['dow']."</td>";
                        echo "<td style='vertical-align: center'>".$row['durata']."</td>";
                        echo "<td style='vertical-align: center'>".$row['max_ploaie']."</td>";
                        echo "<td style='vertical-align: center'>".$row['ploaie']."</td>";
                        echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='execute' value='".$row['id']."' class='btn btn-danger'>Executa ACUM!</button></td>";
                        echo "</tr>";
                    }
                }
                mysqli_free_result($result);
                if (isset($_POST['addnew'])) {
                    $sql = "SELECT id, denumire FROM trasee;";
                    $result = mysqli_query($conn, $sql);
                    echo "<tr>";
                    echo "<td style='vertical-align: center'>NOU</td>";
                    echo "<td><select name='traseu' class='form-control'>";
                    $trow = mysqli_fetch_array($result, MYSQLI_ASSOC);
                    echo "<option value='".$trow['id']."' selected>".$trow['denumire']."</option>";
                    while ($trow = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
                        echo "<option value='".$trow['id']."'>".$trow['denumire']."</option>";
                    }
                    echo "</select></td>";
                    echo "<td><input type='text' name='h' class='form-control' value='6' style='width: min-content'></td>";
                    echo "<td><input type='text' name='m' class='form-control' value='0' style='width: min-content'></td>";
                    echo "<td><input type='text' name='dom' class='form-control' value='*' style='width: min-content'></td>";
                    echo "<td><input type='text' name='mon' class='form-control' value='*' style='width: min-content'></td>";
                    echo "<td><input type='text' name='dow' class='form-control' value='*' style='width: min-content'></td>";
                    echo "<td><input type='number' name='durata' class='form-control' value='5'></td>";
                    echo "<td><input type='number' name='max_ploaie' class='form-control' value='4'></td>";
                    echo "<td style='vertical-align: center'>N/A</td>";
                    echo "<td><button style='max-height: 20px; padding-top: 0' type='submit' name='insert' value='introdu' class='btn btn-success'>Introdu</button>";
                    echo "</tr>";
                    mysqli_free_result($result);
                }
                ?>
            </table>
        </div>
        <div class="row">
            <div class="col-md-9"></div>
            <div class="col-md-1"><a href="help.php" class="btn btn-info" role="button">Sintaxa</a></div>
            <div class="col-md-2"><button type="submit" name="addnew" value="nou" class="btn btn-primary">Adauga</button></div>
        </div>
    </form>
</div>
<?php
if (isset($_POST['insert'])) {
    $stmt = mysqli_prepare($conn, "INSERT INTO programari (traseu_id, h, m, dom, mon, dow, durata, max_ploaie) VALUES (?, ?, ?, ?, ?, ?, ?, ?);");
    if (!$stmt) {
        die ("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_error($conn)."}</pre>");
    }
    mysqli_stmt_bind_param($stmt, "isssssii", $_POST['traseu'], $_POST['h'], $_POST['m'], $_POST['dom'], $_POST['mon'], $_POST['dow'], $_POST['durata'], $_POST['max_ploaie']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    if (file_exists('/tmp/crontab.txt')) unlink('/tmp/crontab.txt');
    $result = mysqli_query($conn, 'SELECT * FROM programari;');
    while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
        file_put_contents('/tmp/crontab.txt', $row['m'].' '.$row['h'].' '.$row['dom'].' '.$row['mon'].' '.$row['dom'].' /home/pi/irigatie/client.py -c START -p '.$row['traseu_id'].PHP_EOL, FILE_APPEND);
    }
    mysqli_free_result($result);
    shell_exec('crontab -r');
    shell_exec('crontab /tmp/crontab.txt');
    //mysqli_close($conn);
    unset($_POST);
    echo "<script>window.location='mainpage.php'</script>";
}
if (isset($_POST['edex'])) {
    $stmt = mysqli_prepare($conn, "UPDATE programari SET traseu_id = ?, h = ?, m = ?, dom = ?, mon = ?, dow = ?, durata = ?, max_ploaie = ? WHERE id = ?;");
    if (!$stmt) {
        die ("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysqli_error($conn)."}</pre>");
    }
    mysqli_stmt_bind_param($stmt, "isssssiii", $_POST['traseu'], $_POST['h'], $_POST['m'], $_POST['dom'], $_POST['mon'], $_POST['dow'], $_POST['durata'], $_POST['max_ploaie'], $_POST['edex']);
    mysqli_stmt_execute($stmt);
    mysqli_stmt_close($stmt);
    if (file_exists('/tmp/crontab.txt')) unlink('/tmp/crontab.txt');
    $result = mysqli_query($conn, 'SELECT * FROM programari;');
    while ($row = mysqli_fetch_array($result, MYSQLI_ASSOC)) {
        file_put_contents('/tmp/crontab.txt', $row['m'].' '.$row['h'].' '.$row['dom'].' '.$row['mon'].' '.$row['dom'].' /home/pi/irigatie/client.py -c START -p '.$row['traseu_id'].PHP_EOL, FILE_APPEND);
    }
    mysqli_free_result($result);
    shell_exec('crontab -r');
    shell_exec('crontab /tmp/crontab.txt');
    unset($_POST);
    echo "<script>window.location='mainpage.php'</script>";
}
if (isset($_POST['execute'])) {
    $sock = socket_create(AF_UNIX, SOCK_DGRAM, 0);
    socket_sendto($sock,'START ' . $_POST['execute'], 7, 0, '/tmp/python_irigatie_unix_socket', 0);
}

mysqli_close($conn);
