<?php
include('header.php');
?>

<div class="container">
    <h2>Sintaxa cron</h2>
    <p>Valori permise per coloana</p>
    <div class="table-responsive">
        <table class="table">
            <thead>
            <tr>
                <th>ORA</th>
                <th>MINUTUL</th>
                <th>ZIUA LUNII</th>
                <th>LUNA</th>
                <th>ZIUA SAPTAMANII</th>
            </tr>
            </thead>
            <tbody>
            <tr>
                <td>0-23</td>
                <td>0-59</td>
                <td>1-31</td>
                <td>1-12 sau nume</td>
                <td>0-7 sau nume (atat 0 cat si 7 inseamna duminica)</td>
            </tr>
            </tbody>
        </table>
    </div>
    <p>Oricare camp poate avea valoarea * (asterisc), care reprezinta intotdeauna "primul-ultimul".</p>
    <p>Sunt permise intervale de numere. Intervalele sunt doua numere seprate cu - (minus). Intervalele specificate includ capetele. De exemplu 8-11 la "ORA" specifica executia la orele 8, 9 ,10 si 11.</p>
    <p>Sunt permise si liste. O lista este un set de numere sau intervale separate cu virgule. Exemple: "1,2,5,9", "0-4,8-12".</p>
    <p>Valorile de pas sunt permise in conjunctie cu intervale. Un "/numar" pus la sfarsitul unui interval specifica cate numere vor fi sarite din interval. De exemplu "0-23/2" poate fi utilizat pentru a specifica executia din doua in doua ore (alternativa ar fi "0,2,4,6,8,10,12,14,16,18,20,22"). Valorile de pas sunt permise si dupa un asteisc, astfel daca vreti sa speficati executia din doua in doua ore puteti utiliza simpl "*/2"</p>
    <p>In coloanele "LUNA" si "ZIUA SAPTAMANII" pot fi folosite si denumiri (nu conteaza capitalizare). Intervalele sau listele de nume nu sunt permise</p>
</div>

