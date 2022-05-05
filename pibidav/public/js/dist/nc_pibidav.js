// Copyright (c) 2022, pibiCo and Contributors
// MIT License. See license.txt

frappe.ui.form.on(doctype.name, {
  after_save: function(frm) {
    // hacer comprobaciones pertinentes y si, por ejemplo, aun no se ha
    // relacionado con NC ese registro ejecutar codigo de extension
    var se_dan_condiciones = true;
    if (se_dan_condiciones) {
      frappe.confirm('Integrar con documentacion en NextCloud?',
        () => {
          frm.trigger("my_app_code");
        }, () => {
          // si procede hacer algo cuando responde que no AQUI
      });
    }
  },
  my_app_code: function(frm){
    // este es un ejemplo  simple, pero aqui abrimos dialogo
    // pediriamos datos, insertariamos en el archivo de extension
    // y hariamos todas las acciones necesarias para nuestra extension
    frappe.prompt([
      {
        label: 'Estructura a copiar',
        fieldname: 'estructura',
        fieldtype: 'Data'
      },
      {
        label: 'Copiar en',
        fieldname: 'raiz',
        fieldtype: 'Data'
      },
      new frappe.ui.pibiDAV
    ], (values) => {
      // datos de link de registro y datos solicitados para nuestra accion
      console.log(doctype.name, frm.doc.name, values.estructura, values.raiz);
    });
  }
});