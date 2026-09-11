const fs = require('fs');
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  await page.setViewport({ width: 800, height: 600 });

  const css = fs.readFileSync('static/fin2.css', 'utf8');
  const html = fs.readFileSync('templates/dashboard/xp_statement.html', 'utf8');

  const fullHtml = `
    <!DOCTYPE html>
    <html><head><style>${css}</style></head>
    <body>
    <main>
    <section class="panel">
    <form>
    ${html}
    </form>
    </section>
    </main>
    </body></html>
  `;

  await page.setContent(fullHtml);
  
  const wraps = await page.$$('.table-wrap');
  for (let i = 0; i < wraps.length; i++) {
    const wrap = wraps[i];
    const clientWidth = await wrap.evaluate(el => el.clientWidth);
    const scrollWidth = await wrap.evaluate(el => el.scrollWidth);
    console.log(`TableWrap ${i}: clientWidth=${clientWidth}, scrollWidth=${scrollWidth}`);
    
    const table = await wrap.$('table');
    if (table) {
      const tableWidth = await table.evaluate(el => el.offsetWidth);
      console.log(`  Table ${i}: offsetWidth=${tableWidth}`);
      
      // Let's check which cell is forcing it
      const cells = await table.$$('th, td');
      let maxCellWidth = 0;
      for (const cell of cells) {
        const cellWidth = await cell.evaluate(el => el.offsetWidth);
        if (cellWidth > maxCellWidth) maxCellWidth = cellWidth;
      }
      console.log(`  Table ${i} max cell width: ${maxCellWidth}`);
    }
  }

  await browser.close();
})();
