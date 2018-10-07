<?php
include('header.php');
$conn = mysqli_connect($ini_array['DB_SERVER'], $ini_array['DB_USER'], $ini_array['DB_PASS'],$ini_array['DB_NAME']);
if (mysqli_connect_errno()) {
    die("<pre style='color:#EE2711'>Failed to connect to MySQL: {".mysql_connect_error()."}</pre>");
}
?>
<div class="container" id="tables" style="margin-left: 20px">
    <div class="row">
        <form action="edit.php" method="POST" id="myForm" onsubmit="window.location.reload()">
            <table class="table table-hover" id="myTable" style="white-space: nowrap">
                <thead>
                <tr>
                    <th style="vertical-align: center">ID</th>
                    <th style="vertical-align: center">TRASEU</th>
                    <th style="vertical-align: center">ORA</th>
                    <th style="vertical-align: center">MINUTUL</th>
                    <th style="vertical-align: center">ZIUA LUNII</th>
                    <th style="vertical-align: center">LUNA</th>
                    <th style="vertical-align: center">ZIUA SAPTAMANII</th>
                    <th style="vertical-align: center">DURATA</th>
                    <th style="vertical-align: center">PLOAIE</th>
                    <th></th>
                </tr>
                </thead>
                <?php
                $sql = "SELECT trasee.denumire, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id;";
                $result = mysqli_query($conn, $sql);
                while ($row=mysqli_fetch_array($result, MYSQLI_ASSOC)) {
                    echo "<tr>";
                    echo "<td><button style='color: blue; background-color: #5cb85c; max-height: 20px; padding-top: 0px' type='submit' name='work' value='".$row['id']."' class='btn btn-default'>".$row['id']."</button></td>";
                    echo "<td style='vertical-align: center'>".$row['denumire']."</td>";
                    echo "<td style='vertical-align: center'>".$row['h']."</td>";
                    echo "<td style='vertical-align: center'>".$row['m']."</td>";
                    echo "<td style='vertical-align: center'>".$row['dom']."</td>";
                    echo "<td style='vertical-align: center'>".$row['mon']."</td>";
                    echo "<td style='vertical-align: center'>".$row['dow']."</td>";
                    echo "<td style='vertical-align: center'>".$row['durata']."</td>";
                    echo "<td style='vertical-align: center'>".$row['ploaie']."</td>";
                    echo "<td><button style='max-height: 20px; padding-top: 0px' type='submit' name='work' value='".$row['id']."' class='btn btn-danger'>Executa ACUM!</button></td>";
                }
                ?>
            </table>
        </form>
    </div>
</div>
