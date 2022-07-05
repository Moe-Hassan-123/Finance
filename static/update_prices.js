function update() {
    var aj = new XMLHttpRequest();
    aj.onreadystatechange = function() {
        if (aj.readyState == 4 && aj.status == 200)
        {
            len = length(stock)
            symbols = new Array(len) 
            stocks = document.getElementsByClassName("price")
            for (let i = 0; i < len; i++) {
                symbols[i] = '';
            }
        }
        aj.open(); // to do
        aj.send();
    }
}
setInterval(update,10000)
